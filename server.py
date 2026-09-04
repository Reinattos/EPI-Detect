#!/usr/bin/env python3
"""
Interface web: transmite o video anotado e expoe as estatisticas por HTTP.

Uso:

    python server.py
    python server.py --source 0
    python server.py --source rtsp://usuario:senha@192.168.0.50:554/stream1
    python server.py --port 8080

Depois abra http://localhost:5000

Cada camera roda em tres threads: captura, deteccao e codificacao. A
separacao existe porque as tres tem ritmos muito diferentes. A camera
entrega 30 quadros por segundo, a deteccao processa entre 2 e 6, e o
navegador consome cerca de 12. Num unico laco, a etapa mais lenta
ditaria o ritmo de todas e o video ficaria travado.

O modelo e uma instancia unica compartilhada, protegida por lock: a
inferencia nao e reentrante e carregar um modelo por camera gastaria
memoria sem ganho.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time

import cv2
from flask import Flask, Response, jsonify, render_template, request

import config
from core.capture import VideoCapture
from core.detector import EPIDetector
from core.overlay import draw_detections, draw_header, draw_live_badge, draw_sidebar, make_canvas
from core.tracker import Tracker, summarize
from core.zones import load_zones, next_color, save_zones

app = Flask(__name__)

_detector: EPIDetector | None = None
_detector_lock = threading.Lock()   # serializa a inferencia
_model_ready = threading.Event()
_pipelines: list[Pipeline] = []
_zones: list = []
_running = True


class Pipeline:
    """Uma camera: captura, detecta e codifica em threads separadas."""

    def __init__(self, source, cam_id: int = 0, name: str | None = None):
        self.source = source
        self.cam_id = cam_id
        self.name = name or f"CAM {cam_id + 1:02d}"

        self._lock = threading.Lock()
        self._tracker = Tracker()
        self._capture: VideoCapture | None = None

        self._frame = None
        self._detections: list = []
        self._jpeg: bytes | None = None
        self._counts = {"ok": 0, "no_vest": 0, "no_helmet": 0, "total": 0}
        self._det_fps = 0.0
        self._stream_fps = 0.0
        self._error: str | None = None
        self._status = "iniciando"

    # ── ciclo de vida ─────────────────────────────────────────────────────────
    def start(self):
        for target in (self._capture_loop, self._detect_loop, self._encode_loop):
            threading.Thread(target=target, daemon=True).start()

    def stats(self) -> dict:
        with self._lock:
            total = self._counts["total"]
            return {
                "camera": self.name,
                "cam_id": self.cam_id,
                **self._counts,
                "compliance": int(self._counts["ok"] / total * 100) if total else 100,
                "det_fps": round(self._det_fps, 1),
                "stream_fps": round(self._stream_fps, 1),
                "status": self._status,
                "error": self._error,
                "people": [
                    {
                        "track_id": d.track_id,
                        "has_vest": d.has_vest,
                        "has_helmet": d.has_helmet,
                        "vest_score": round(d.vest_score, 3),
                        "helmet_score": round(d.helmet_score, 3),
                        "violation_seconds": round(
                            d.violation_frames / max(config.STREAM_FPS, 1), 1),
                    }
                    for d in self._detections
                ],
            }

    def jpeg(self) -> bytes | None:
        with self._lock:
            return self._jpeg

    # ── threads ───────────────────────────────────────────────────────────────
    def _capture_loop(self):
        while _running:
            try:
                self._capture = VideoCapture(self.source,
                                             width=config.FRAME_WIDTH,
                                             height=config.FRAME_HEIGHT,
                                             fps=config.TARGET_FPS)
                with self._lock:
                    self._error = None
                    self._status = "capturando"

                while _running:
                    ok, frame = self._capture.read()
                    if not ok:
                        break
                    with self._lock:
                        self._frame = frame
                    time.sleep(1.0 / max(config.TARGET_FPS, 1))

            except Exception as exc:
                with self._lock:
                    self._error = f"captura: {exc}"
                    self._status = "erro"
            finally:
                if self._capture:
                    self._capture.release()
            # reconecta: camera IP cai e volta, nao faz sentido morrer por isso
            time.sleep(2.0)

    def _detect_loop(self):
        _model_ready.wait()
        with self._lock:
            self._status = "detectando"

        timestamps: list[float] = []
        last = None

        while _running:
            with self._lock:
                frame = self._frame
            if frame is None or frame is last:
                time.sleep(0.01)
                continue
            last = frame

            try:
                with _detector_lock:
                    detections = _detector.detect(frame)
            except Exception as exc:
                with self._lock:
                    self._error = f"inferencia: {exc}"
                    self._status = "erro"
                time.sleep(0.5)
                continue

            # o tracker e por camera: identidades nao se misturam
            detections = self._tracker.update(detections, config.STREAM_FPS)
            zoned = _apply_zones(detections, frame.shape[1], frame.shape[0])

            now = time.perf_counter()
            timestamps.append(now)
            timestamps = [t for t in timestamps if now - t < 1.0]

            with self._lock:
                self._detections = zoned
                self._counts = summarize(zoned)
                self._det_fps = len(timestamps)
                self._error = None

    def _encode_loop(self):
        interval = 1.0 / max(config.STREAM_FPS, 1)
        timestamps: list[float] = []
        last = None
        index = 0

        while _running:
            started = time.perf_counter()
            with self._lock:
                frame = self._frame
                detections = list(self._detections)
                counts = dict(self._counts)
                det_fps = self._det_fps

            if frame is None:
                time.sleep(0.05)
                continue

            if frame is not last:
                last = frame
                canvas = make_canvas(frame)
                draw_detections(canvas, detections, config.STREAM_FPS,
                                frame.shape[1])
                draw_header(canvas, self.name, time.strftime("%H:%M:%S"))
                draw_live_badge(canvas, blink=(index // 6) % 2 == 0)
                draw_sidebar(canvas, counts, det_fps,
                             pulse=abs((index % 20) / 10.0 - 1.0))

                ok, buffer = cv2.imencode(
                    ".jpg", canvas, [cv2.IMWRITE_JPEG_QUALITY, config.JPEG_QUALITY])
                if ok:
                    now = time.perf_counter()
                    timestamps.append(now)
                    timestamps = [t for t in timestamps if now - t < 1.0]
                    with self._lock:
                        self._jpeg = buffer.tobytes()
                        self._stream_fps = len(timestamps)
                index += 1

            elapsed = time.perf_counter() - started
            time.sleep(max(0.0, interval - elapsed))


def _apply_zones(detections, width: int, height: int):
    """Anota cada deteccao com as zonas em que ela viola o exigido."""
    if not _zones:
        return detections
    try:
        from core.zones import person_zone_violations
    except ImportError:
        return detections
    for det in detections:
        det.zones = person_zone_violations(det, _zones, width, height)
    return detections


def _load_model():
    """Carrega o modelo em background para o servidor subir na hora."""
    global _detector
    try:
        print("Carregando modelo (a primeira execucao baixa os pesos)...")
        started = time.time()
        _detector = EPIDetector()
        print(f"Modelo pronto em {time.time() - started:.1f}s")
    except Exception as exc:
        print(f"Falha ao carregar o modelo: {exc}", file=sys.stderr)
    finally:
        _model_ready.set()


def _pipeline(cam_id: int) -> Pipeline | None:
    return _pipelines[cam_id] if 0 <= cam_id < len(_pipelines) else None


def _mjpeg(pipe: Pipeline):
    boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
    while _running:
        data = pipe.jpeg()
        if data:
            yield boundary + data + b"\r\n"
        time.sleep(1.0 / max(config.STREAM_FPS, 1))


# ── rotas ─────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html",
                           title=config.SYSTEM_TITLE,
                           cameras=[p.name for p in _pipelines])


@app.route("/video_feed")
@app.route("/video_feed/<int:cam_id>")
def video_feed(cam_id: int = 0):
    pipe = _pipeline(cam_id)
    if pipe is None:
        return jsonify({"error": "camera inexistente"}), 404
    return Response(_mjpeg(pipe),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/stats")
@app.route("/stats/<int:cam_id>")
def stats(cam_id: int = 0):
    pipe = _pipeline(cam_id)
    if pipe is None:
        return jsonify({"error": "camera inexistente"}), 404
    return jsonify(pipe.stats())


@app.route("/health")
def health():
    return jsonify({
        "status": "ok" if _model_ready.is_set() else "carregando",
        "model": config.MODEL_PATH,
        "imgsz": _detector.imgsz if _detector else None,
        "cameras": len(_pipelines),
    })


@app.route("/api/cameras")
def cameras():
    return jsonify([p.stats() for p in _pipelines])


@app.route("/api/zones", methods=["GET", "POST"])
def zones():
    global _zones
    if request.method == "GET":
        return jsonify(_zones)

    payload = request.get_json(silent=True) or {}
    action = payload.get("action")

    if action == "add":
        zone = payload.get("zone", {})
        zone.setdefault("color", next_color(len(_zones)))
        _zones.append(zone)
    elif action == "update":
        index = payload.get("index", -1)
        if 0 <= index < len(_zones):
            _zones[index].update(payload.get("zone", {}))
    elif action == "delete":
        index = payload.get("index", -1)
        if 0 <= index < len(_zones):
            _zones.pop(index)
    elif action == "replace_all":
        _zones = payload.get("zones", [])
    else:
        return jsonify({"error": "acao invalida"}), 400

    save_zones(_zones)
    return jsonify(_zones)


@app.route("/api/settings", methods=["GET", "POST"])
def settings():
    """Le e grava os limites ajustaveis em settings_local.json."""
    keys = ("CONF_THRESH", "VEST_THRESH", "HELMET_THRESH",
            "STABILIZE_WINDOW", "SHOW_ANALYSIS_ZONES",
            "INPUT_SIZE", "STREAM_FPS", "JPEG_QUALITY")

    if request.method == "GET":
        return jsonify({k: getattr(config, k) for k in keys})

    payload = request.get_json(silent=True) or {}
    applied = {}
    for key, value in payload.items():
        if key in keys:
            setattr(config, key, value)
            applied[key] = value

    if applied:
        import json
        current = {}
        if config.LOCAL_SETTINGS.exists():
            try:
                current = json.loads(config.LOCAL_SETTINGS.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                current = {}
        current.update(applied)
        config.LOCAL_SETTINGS.write_text(
            json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")

    return jsonify({"applied": applied})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Servidor web do EPI Detect")
    parser.add_argument("--source", action="append", default=None,
                        help="fonte de video; repita a opcao para varias cameras")
    parser.add_argument("--port", type=int, default=config.PORT)
    parser.add_argument("--host", default=config.HOST)
    return parser.parse_args()


def main() -> int:
    global _zones, _running

    args = parse_args()
    sources = args.source or [config.SOURCE]
    _zones = load_zones()

    threading.Thread(target=_load_model, daemon=True).start()

    for cam_id, source in enumerate(sources):
        resolved = int(source) if str(source).isdigit() else source
        pipe = Pipeline(resolved, cam_id)
        pipe.start()
        _pipelines.append(pipe)
        print(f"{pipe.name}: {resolved}")

    url = f"http://localhost:{args.port}"
    print(f"\nServidor em {url}")
    print("O video aparece assim que o modelo terminar de carregar.\n")

    try:
        app.run(host=args.host, port=args.port, threaded=True,
                debug=False, use_reloader=False)
    except KeyboardInterrupt:
        pass
    finally:
        _running = False
    return 0


if __name__ == "__main__":
    sys.exit(main())
