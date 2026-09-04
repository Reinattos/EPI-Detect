#!/usr/bin/env python3
"""
Deteccao ao vivo numa janela do sistema.

Uso tipico:

    python detect.py                  # webcam padrao
    python detect.py --source 1       # segunda webcam
    python detect.py --source video.mp4
    python detect.py --source rtsp://user:senha@192.168.0.50:554/stream1

Teclas: Q ou ESC encerra, Z liga/desliga as zonas de analise, ESPACO pausa.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime

import cv2

import config
from core.detector import EPIDetector
from core.overlay import draw_detections, draw_header, draw_live_badge, draw_sidebar, make_canvas
from core.tracker import Tracker, summarize


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Deteccao de EPI ao vivo (colete refletivo e capacete)")
    parser.add_argument("--source", default=None,
                        help="indice de webcam, arquivo de video ou URL RTSP "
                             f"(padrao: {config.SOURCE})")
    parser.add_argument("--imgsz", type=int, default=None,
                        help="resolucao de entrada do modelo; menor e mais "
                             f"rapido (padrao: {config.INPUT_SIZE})")
    parser.add_argument("--camera-name", default="CAM 01",
                        help="rotulo exibido no cabecalho")
    parser.add_argument("--no-zones", action="store_true",
                        help="oculta as caixas tracejadas de analise")
    return parser.parse_args()


def resolve_source(value):
    """Indice de webcam vem como int; arquivo e RTSP continuam string."""
    if value is None:
        return config.SOURCE
    return int(value) if str(value).isdigit() else value


def main() -> int:
    args = parse_args()
    if args.no_zones:
        config.SHOW_ANALYSIS_ZONES = False

    source = resolve_source(args.source)
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"Nao foi possivel abrir a fonte: {source}", file=sys.stderr)
        print("Se for webcam, verifique se outro programa esta usando a camera.",
              file=sys.stderr)
        return 1

    if isinstance(source, int):
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
        cap.set(cv2.CAP_PROP_FPS, config.TARGET_FPS)

    print("Carregando modelo (a primeira execucao baixa os pesos)...")
    detector = EPIDetector(imgsz=args.imgsz)
    tracker = Tracker()

    window = "EPI Detect  |  Q para sair"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)

    fps_estimate = 0.0
    frame_index = 0
    paused = False

    while True:
        if not paused:
            ok, frame = cap.read()
            if not ok:
                break

            started = time.perf_counter()
            detections = tracker.update(detector.detect(frame))
            elapsed = time.perf_counter() - started
            # media exponencial: numero estavel o suficiente para ler na tela
            instant = 1.0 / max(elapsed, 1e-6)
            fps_estimate = instant if not fps_estimate else fps_estimate * 0.8 + instant * 0.2

            counts = summarize(detections)
            video_width = frame.shape[1]
            canvas = make_canvas(frame)

            draw_detections(canvas, detections, config.TARGET_FPS, video_width)
            draw_header(canvas, args.camera_name,
                        datetime.now().strftime("%H:%M:%S"))
            draw_live_badge(canvas, blink=(frame_index // 12) % 2 == 0)
            draw_sidebar(canvas, counts, fps_estimate,
                         pulse=abs((frame_index % 20) / 10.0 - 1.0))

            cv2.imshow(window, canvas)
            frame_index += 1

        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            break
        if key == ord("z"):
            config.SHOW_ANALYSIS_ZONES = not config.SHOW_ANALYSIS_ZONES
        if key == ord(" "):
            paused = not paused

    cap.release()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
