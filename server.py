"""
server.py -- EPI Detect Web Dashboard
Acesse: http://localhost:5000

Pipeline assincrono:
  Thread 1 (capture) — mantem o frame mais recente da camera/video
  Thread 2 (detect)  — roda YOLO + HSV sem bloquear o stream
  Thread 3 (encode)  — renderiza e gera JPEG a STREAM_FPS
  Flask              — serve MJPEG + stats
"""

import argparse
import sys
import threading
import time
from pathlib import Path

import cv2
from flask import Flask, Response, jsonify, render_template

sys.path.insert(0, str(Path(__file__).parent))

import config as cfg
from core.capture import VideoCapture
from core.detector import EPIDetector
from core.display import Renderer

DEMO_VIDEO    = Path(__file__).parent / "demo" / "HappyHorse-20260820-0001-1787264992984.mp4"
DEMO_RENDERED = Path(__file__).parent / "demo" / "demo_linkedin.mp4"   # H.264, decode rapido
DEMO_STATS    = Path(__file__).parent / "demo" / "demo_stats.json"

app = Flask(__name__)
_lock = threading.Lock()

# estado compartilhado entre threads
_state = {
    "raw_frame": None,
    "detections": [],
    "jpeg": None,  # bytes        — escrito por encode, lido por Flask
    "with_vest": 0,
    "without_vest": 0,
    "total": 0,
    "det_fps": 0,  # FPS da detecção
    "stream_fps": 0,  # FPS do stream
    "mode": "DEMO",
    "alert": False,
    "camera_ready": False,
    "model_ready": False,
    "status": "starting",
    "error": None,
    "playback_mode": False,   # True = frame já renderizado, encode só faz JPEG
}
_running = True


def _refresh_status_locked():
    """Atualiza o estado publico; deve ser chamado com `_lock` adquirido."""
    if _state["error"]:
        _state["status"] = "error"
    elif not _state["camera_ready"]:
        _state["status"] = "waiting_camera"
    elif not _state["model_ready"]:
        _state["status"] = "loading_model"
    else:
        _state["status"] = "running"


def _box_iou(det, track) -> float:
    ax1, ay1, ax2, ay2 = det.x1, det.y1, det.x2, det.y2
    bx1, by1, bx2, by2 = track["box"]
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / union if union > 0 else 0.0


def _stabilize_detections(detections, tracks, frame_index):
    """Usa maioria temporal de 5 analises, associando pessoas por IoU."""
    used = set()
    for det in detections:
        candidates = [(i, _box_iou(det, track)) for i, track in enumerate(tracks) if i not in used]
        best_i, best_iou = max(candidates, key=lambda item: item[1], default=(-1, 0.0))
        if best_iou < 0.30:
            tracks.append(
                {"box": (det.x1, det.y1, det.x2, det.y2), "votes": [], "last": frame_index}
            )
            best_i = len(tracks) - 1

        track = tracks[best_i]
        used.add(best_i)
        track["box"] = (det.x1, det.y1, det.x2, det.y2)
        track["last"] = frame_index
        track["votes"].append(bool(det.has_vest))
        track["votes"] = track["votes"][-5:]
        if len(track["votes"]) >= 3:
            det.has_vest = sum(track["votes"]) > len(track["votes"]) / 2

    tracks[:] = [t for t in tracks if frame_index - t["last"] <= 10]
    return detections


# ── Thread: playback de vídeo pré-renderizado (sem YOLO) ─────────────────────
def _playback_loop():
    """Serve demo_output.mp4 em loop a 25 fps — suave, sem inferência em tempo real."""
    global _running
    import json as _json

    print("[playback] iniciando modo DEMO pré-renderizado", flush=True)

    frame_stats: list = []
    if DEMO_STATS.exists():
        try:
            frame_stats = _json.loads(DEMO_STATS.read_text())
        except Exception:
            pass

    with _lock:
        _state["model_ready"] = True
        _state["camera_ready"] = True
        _state["status"] = "running"
        _state["playback_mode"] = True

    target_dt = 1.0 / 25.0
    fps_times: list = []

    while _running:
        cap = cv2.VideoCapture(str(DEMO_RENDERED))
        if not cap.isOpened():
            print("[playback] erro ao abrir demo_output.mp4", flush=True)
            _running = False
            return

        frame_n = 0
        while _running:
            t0 = time.perf_counter()
            ok, frame = cap.read()
            if not ok:
                break

            s = frame_stats[frame_n % len(frame_stats)] if frame_stats else {}

            now = time.perf_counter()
            fps_times.append(now)
            fps_times[:] = [t for t in fps_times if now - t < 1.0]

            with _lock:
                _state["raw_frame"]    = frame
                _state["with_vest"]    = s.get("with_vest", 0)
                _state["without_vest"] = s.get("without_vest", 0)
                _state["total"]        = s.get("total", 0)
                _state["det_fps"]      = len(fps_times)
                _state["alert"]        = s.get("alert", False)

            frame_n += 1
            elapsed = time.perf_counter() - t0
            sleep = target_dt - elapsed
            if sleep > 0:
                time.sleep(sleep)

        cap.release()


# ── Thread 1: captura ─────────────────────────────────────────────────────────
def _capture_loop(source, mode: str):
    global _running
    while _running:
        try:
            cap = VideoCapture(
                source,
                width=cfg.WEBCAM_WIDTH if isinstance(source, int) else None,
                height=cfg.WEBCAM_HEIGHT if isinstance(source, int) else None,
                fps=cfg.WEBCAM_FPS if isinstance(source, int) else None,
            )
        except RuntimeError as e:
            message = str(e)
            print(f"[capture] {message}", flush=True)
            with _lock:
                _state["camera_ready"] = False
                _state["error"] = message
                _refresh_status_locked()
            time.sleep(2)
            continue

        frame_delay = 1.0 / (cap.fps if mode == "DEMO" else cfg.STREAM_FPS)
        while _running:
            started = time.perf_counter()
            try:
                ok, frame = cap.read()
            except Exception as e:
                print(f"[capture] cap.read erro: {e}", flush=True)
                break
            if not ok:
                break

            with _lock:
                _state["raw_frame"] = frame
                _state["camera_ready"] = True
                _state["error"] = None
                _refresh_status_locked()

            remaining = frame_delay - (time.perf_counter() - started)
            if remaining > 0:
                time.sleep(remaining)

        cap.release()
        if _running and mode != "DEMO":
            time.sleep(0.5)


def _detect_loop():
    global _running
    try:
        det = EPIDetector()
    except Exception as e:
        import traceback

        print(f"[detect] ERRO ao iniciar: {e}", flush=True)
        traceback.print_exc()
        with _lock:
            _state["model_ready"] = False
            _state["error"] = f"Falha ao carregar o modelo: {e}"
            _refresh_status_locked()
        return
    print("[detect] modelo carregado", flush=True)
    with _lock:
        _state["model_ready"] = True
        _state["error"] = None
        _refresh_status_locked()

    det_times: list = []
    last_frame = None
    tracks = []
    frame_index = 0
    while _running:
        cycle_start = time.perf_counter()
        with _lock:
            frame = _state["raw_frame"]

        if frame is None or frame is last_frame:
            time.sleep(0.01)
            continue

        try:
            detections = det.detect(frame)
        except Exception as e:
            print(f"[detect] inferencia falhou: {e}", flush=True)
            with _lock:
                _state["error"] = f"Falha temporaria na inferencia: {e}"
                _refresh_status_locked()
            time.sleep(0.2)
            continue
        last_frame = frame
        frame_index += 1
        detections = _stabilize_detections(detections, tracks, frame_index)

        now = time.perf_counter()
        det_times.append(now)
        det_times = [t for t in det_times if now - t < 1.0]
        with_v = sum(1 for d in detections if d.has_vest)
        wout_v = len(detections) - with_v
        with _lock:
            _state["error"] = None
            _state["detections"] = detections
            _state["with_vest"] = with_v
            _state["without_vest"] = wout_v
            _state["total"] = len(detections)
            _state["det_fps"] = len(det_times)
            _state["alert"] = wout_v > 0
            _refresh_status_locked()

        remaining = cfg.DETECTION_INTERVAL - (time.perf_counter() - cycle_start)
        if remaining > 0:
            time.sleep(remaining)


# ── Thread 2: encoder JPEG (roda a STREAM_FPS) ───────────────────────────────
def _encode_loop(mode: str):
    global _running
    target = 1.0 / cfg.STREAM_FPS
    enc_times: list = []
    last_arr = None
    renderer = Renderer(mode=mode)

    while _running:
        t0 = time.perf_counter()

        with _lock:
            arr = _state["raw_frame"]
            detections = list(_state["detections"])

        if arr is None:
            time.sleep(0.02)
            continue

        # só reencoda se o frame mudou (evita CPU desperdicada)
        if arr is not last_arr:
            with _lock:
                is_playback = _state["playback_mode"]
            # Em playback o frame já vem renderizado — só faz JPEG
            rendered = arr if is_playback else renderer.render(arr, detections)
            ok, buf = cv2.imencode(".jpg", rendered, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if ok:
                now = time.perf_counter()
                enc_times.append(now)
                enc_times = [t for t in enc_times if now - t < 1.0]
                with _lock:
                    _state["jpeg"] = buf.tobytes()
                    _state["stream_fps"] = len(enc_times)
                last_arr = arr

        elapsed = time.perf_counter() - t0
        sleep = target - elapsed
        if sleep > 0:
            time.sleep(sleep)


# ── MJPEG generator ──────────────────────────────────────────────────────────
def _gen():
    while True:
        with _lock:
            frame = _state["jpeg"]
        if frame is None:
            time.sleep(0.04)
            continue
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
        time.sleep(1 / cfg.STREAM_FPS)


# ── rotas Flask ───────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html", mode=_state["mode"])


@app.route("/video_feed")
def video_feed():
    return Response(_gen(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/stats")
def stats():
    with _lock:
        return jsonify(
            {
                "with_vest": _state["with_vest"],
                "without_vest": _state["without_vest"],
                "total": _state["total"],
                "fps": _state["stream_fps"],
                "det_fps": _state["det_fps"],
                "alert": _state["alert"],
                "status": _state["status"],
                "error": _state["error"],
            }
        )


@app.route("/health")
def health():
    with _lock:
        payload = {
            "ok": _state["status"] != "error",
            "status": _state["status"],
            "camera_ready": _state["camera_ready"],
            "model_ready": _state["model_ready"],
        }
        return jsonify(payload), (200 if payload["ok"] else 503)


# ── main ─────────────────────────────────────────────────────────────────────
def resolve_source(src: str):
    if src in ("webcam", "0"):
        return 0, "LIVE"
    if src == "demo":
        if not DEMO_VIDEO.exists():
            sys.exit(f"[erro] Demo nao encontrado: {DEMO_VIDEO}")
        return str(DEMO_VIDEO), "DEMO"
    if src.isdigit():
        return int(src), "LIVE"
    p = Path(src)
    if not p.exists():
        sys.exit(f"[erro] Arquivo nao encontrado: {p}")
    return str(p), "DEMO"


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", default="webcam")
    p.add_argument("--port", default=5000, type=int)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--no-browser", action="store_true")
    args = p.parse_args()

    source, mode = resolve_source(args.source)
    _state["mode"] = mode

    print("\n  EPI Detect")
    print(f"  Fonte  : {source}")
    print(f"  Modo   : {mode}")
    print(f"  URL    : http://localhost:{args.port}")
    print(f"  Stream : {cfg.STREAM_FPS} fps alvo\n")

    use_playback = (mode == "DEMO" and DEMO_RENDERED.exists())
    if use_playback:
        print("  [PLAYBACK] demo_output.mp4 encontrado — servindo video pre-renderizado\n")
        threading.Thread(target=_playback_loop, daemon=True).start()
    else:
        threading.Thread(target=_capture_loop, args=(source, mode), daemon=True).start()
        threading.Thread(target=_detect_loop, daemon=True).start()
    threading.Thread(target=_encode_loop, args=(mode,), daemon=True).start()

    if not args.no_browser:
        import webbrowser

        time.sleep(2.0)
        webbrowser.open(f"http://localhost:{args.port}")

    app.run(host=args.host, port=args.port, debug=False, threaded=True)
