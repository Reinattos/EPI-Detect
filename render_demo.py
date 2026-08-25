"""
render_demo.py — Pré-renderiza o vídeo DEMO com detecção EPI de qualidade máxima.

Uso:
    python render_demo.py

Saída:
    demo/demo_output.mp4   — vídeo com overlays renderizados (skeleton + bbox torso + labels)
    demo/demo_stats.json   — stats por frame para o playback sincronizado

Após rodar, o servidor em modo DEMO serve o vídeo a 25 fps suave, sem YOLO em tempo real.
"""
import json
import sys
import time
from pathlib import Path

import cv2

_ROOT = Path(__file__).parent
sys.path.insert(0, str(_ROOT))

import config as cfg
from core.detector import EPIDetector
from core.display import Renderer

SRC_VIDEO = _ROOT / "demo" / "HappyHorse-20260820-0001-1787264992984.mp4"
OUT_VIDEO = _ROOT / "demo" / "demo_output.mp4"
OUT_STATS = _ROOT / "demo" / "demo_stats.json"


def main():
    if not SRC_VIDEO.exists():
        sys.exit(f"[erro] Video fonte nao encontrado: {SRC_VIDEO}")

    cap = cv2.VideoCapture(str(SRC_VIDEO))
    fps_src = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(OUT_VIDEO), fourcc, fps_src, (w, h))

    print(f"\n  EPI Detector — RENDER DEMO")
    print(f"  Fonte      : {SRC_VIDEO.name}")
    print(f"  Saida      : {OUT_VIDEO}")
    print(f"  Frames     : {total}  |  {fps_src:.1f} fps")
    print(f"  Resolucao  : {w}x{h}")
    print()

    # Qualidade maxima offline: INPUT 640, detecta a cada 2 frames
    cfg.INPUT_SIZE = 640
    cfg.CONF_THRESH = 0.18

    print("  Carregando modelo YOLO pose... ", end="", flush=True)
    det = EPIDetector()
    renderer = Renderer(mode="DEMO")
    print("pronto.\n")

    stats_list: list = []
    last_dets: list = []
    frame_n = 0
    t_start = time.perf_counter()

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame_n += 1

        # Detecta em todos os frames pares (qualidade maxima offline)
        if frame_n % 2 == 0:
            last_dets = det.detect(frame)

        rendered = renderer.render(frame, last_dets)
        writer.write(rendered)

        with_v = sum(1 for d in last_dets if d.has_vest)
        wout_v = sum(1 for d in last_dets if not d.has_vest)
        stats_list.append(
            {
                "with_vest": with_v,
                "without_vest": wout_v,
                "total": len(last_dets),
                "alert": wout_v > 0,
            }
        )

        if frame_n % 30 == 0 or frame_n == total:
            pct = frame_n / total * 100 if total else 0
            elapsed = time.perf_counter() - t_start
            fps_proc = frame_n / elapsed if elapsed > 0 else 0
            eta = (total - frame_n) / fps_proc if fps_proc > 0 else 0
            bar = "#" * int(pct / 5) + "-" * (20 - int(pct / 5))
            print(
                f"  [{bar}] {pct:5.1f}%  frame {frame_n}/{total}"
                f"  {fps_proc:.1f} fps  ETA {eta:.0f}s    ",
                end="\r",
                flush=True,
            )

    cap.release()
    writer.release()
    OUT_STATS.write_text(json.dumps(stats_list, separators=(",", ":")))

    elapsed = time.perf_counter() - t_start
    print(f"\n\n  Pronto em {elapsed:.0f}s!")
    print(f"  Video : {OUT_VIDEO}")
    print(f"  Stats : {OUT_STATS}")
    print(f"\n  Agora rode:  python server.py --source demo\n")


if __name__ == "__main__":
    main()
