#!/usr/bin/env python3
"""
Processa um arquivo de video e grava o resultado anotado em MP4.

Uso:

    python render.py entrada.mp4
    python render.py entrada.mp4 saida.mp4 --camera-name "CAM 02"

A resolucao de entrada do modelo e escolhida automaticamente medindo
quanto do quadro as pessoas ocupam, porque plano aberto e plano fechado
pedem valores diferentes. Use --imgsz para fixar manualmente.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

import config
from core.detector import EPIDetector, pick_input_size
from core.overlay import (
    blur_region,
    draw_detections,
    draw_header,
    draw_live_badge,
    draw_sidebar,
    make_canvas,
)
from core.tracker import Tracker, summarize


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Renderiza um video com as anotacoes de EPI")
    parser.add_argument("input", help="arquivo de video de entrada")
    parser.add_argument("output", nargs="?", default=None,
                        help="arquivo de saida (padrao: <entrada>_epi.mp4)")
    parser.add_argument("--imgsz", type=int, default=None,
                        help="fixa a resolucao do modelo em vez de detectar")
    parser.add_argument("--camera-name", default="CAM 01",
                        help="rotulo exibido no cabecalho")
    parser.add_argument("--no-zones", action="store_true",
                        help="oculta as caixas tracejadas de analise")
    parser.add_argument("--blur", metavar="X1,Y1,X2,Y2", default=None,
                        help="desfoca um retangulo, para cobrir marca de agua "
                             "ou relogio gravado no video de origem")
    parser.add_argument("--crop-top", type=int, default=0, metavar="N",
                        help="corta N pixels do topo antes de processar")
    parser.add_argument("--crop-bottom", type=int, default=0, metavar="N",
                        help="corta N pixels da base antes de processar; util "
                             "quando ha marca de agua ou rodape gravado")
    parser.add_argument("--crop-right", type=int, default=0, metavar="N",
                        help="corta N pixels da direita antes de processar")
    parser.add_argument("--clock-start", default="14:32:00",
                        help="hora inicial exibida no cabecalho (HH:MM:SS)")
    return parser.parse_args()


def parse_blur(value: str | None):
    if not value:
        return None
    try:
        x1, y1, x2, y2 = (int(v) for v in value.split(","))
        return (x1, y1, x2, y2)
    except ValueError:
        raise SystemExit("--blur espera quatro inteiros: X1,Y1,X2,Y2") from None


def parse_clock(value: str) -> int:
    try:
        h, m, s = (int(v) for v in value.split(":"))
        return h * 3600 + m * 60 + s
    except ValueError:
        raise SystemExit("--clock-start espera o formato HH:MM:SS") from None


def main() -> int:
    args = parse_args()
    if args.no_zones:
        config.SHOW_ANALYSIS_ZONES = False

    src = Path(args.input)
    if not src.exists():
        print(f"Arquivo nao encontrado: {src}", file=sys.stderr)
        return 1

    dst = Path(args.output) if args.output else src.with_name(f"{src.stem}_epi.mp4")
    blur_box = parse_blur(args.blur)
    clock_base = parse_clock(args.clock_start)

    cap = cv2.VideoCapture(str(src))
    if not cap.isOpened():
        print(f"Nao foi possivel abrir: {src}", file=sys.stderr)
        return 1

    src_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    src_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # recorta antes de detectar: o modelo nao gasta tempo com a faixa
    # descartada e as coordenadas ja saem no sistema do quadro final
    top = max(0, args.crop_top)
    width = max(64, src_width - max(0, args.crop_right))
    height = max(64, src_height - top - max(0, args.crop_bottom))

    print("Carregando modelo (a primeira execucao baixa os pesos)...")
    detector = EPIDetector(imgsz=args.imgsz)

    if args.imgsz:
        imgsz, median = args.imgsz, 0.0
        scene = "fixado via --imgsz"
    else:
        imgsz, median = pick_input_size(detector.model, cap, total, height)
        detector.imgsz = imgsz
        scene = "plano fechado" if imgsz == config.INPUT_SIZE_NEAR else "plano aberto"

    cropped = (width, height) != (src_width, src_height)
    if cropped:
        print(f"Video : {src_width}x{src_height} -> recortado para "
              f"{width}x{height} @ {fps:.1f} fps | {total} frames")
    else:
        print(f"Video : {width}x{height} @ {fps:.1f} fps | {total} frames")
    if median:
        print(f"Cena  : pessoas ocupam {median * 100:.0f}% da altura "
              f"-> imgsz={imgsz} ({scene})")
    else:
        print(f"Cena  : imgsz={imgsz} ({scene})")
    print(f"Saida : {dst}")

    # o painel vai AO LADO do video, nao sobre ele: nada do quadro
    # original e coberto, incluindo marca de agua no canto
    out_width = width + config.SIDEBAR_WIDTH
    writer = cv2.VideoWriter(str(dst), cv2.VideoWriter_fourcc(*"mp4v"),
                             fps, (out_width, height))
    print(f"Tela  : {out_width}x{height} (video {width} + painel "
          f"{config.SIDEBAR_WIDTH})")
    tracker = Tracker()
    started = time.time()
    index = 0
    peak = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        if cropped:
            frame = frame[top:top + height, :width]

        frame_started = time.perf_counter()
        detections = tracker.update(detector.detect(frame), fps)
        frame_fps = 1.0 / max(time.perf_counter() - frame_started, 1e-6)

        counts = summarize(detections)
        peak = max(peak, counts["total"])

        if blur_box:
            blur_region(frame, blur_box)

        canvas = make_canvas(frame)
        video_width = width

        seconds = clock_base + int(index / max(fps, 1))
        clock = f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"

        draw_detections(canvas, detections, fps, video_width)
        draw_header(canvas, args.camera_name, clock, index / max(total, 1))
        draw_live_badge(canvas, blink=(index // 12) % 2 == 0)
        draw_sidebar(canvas, counts, frame_fps, pulse=abs(np.sin(index * 0.22)))

        writer.write(canvas)
        index += 1

        if index % 15 == 0:
            elapsed = time.time() - started
            eta = (total - index) / (index / elapsed) if index else 0
            print(f"  {index / max(total, 1) * 100:5.1f}%  {index}/{total} "
                  f"frames | {counts['total']} pessoas | faltam {eta:.0f}s   ",
                  end="\r")

    cap.release()
    writer.release()
    print(f"\nConcluido em {time.time() - started:.0f}s | "
          f"pico de {peak} pessoas simultaneas")
    print(f"Salvo em: {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
