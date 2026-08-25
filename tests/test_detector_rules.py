import cv2
import numpy as np

import config as cfg
from core.detector import EPIDetector, is_vest_evidence


def test_bilateral_evidence_is_required():
    assert not is_vest_evidence(0.05, 0.10, 0.0)
    assert not is_vest_evidence(0.05, 0.0, 0.10)
    assert is_vest_evidence(0.05, 0.05, 0.05)


def test_thresholds_are_inclusive():
    assert is_vest_evidence(
        cfg.VEST_THRESH,
        cfg.VEST_SIDE_THRESH,
        cfg.VEST_SIDE_THRESH,
    )


def test_hsv_metrics_distinguish_one_and_two_sides():
    detector = EPIDetector.__new__(EPIDetector)
    torso = np.zeros((100, 100, 3), dtype=np.uint8)
    fluorescent_yellow_bgr = cv2.cvtColor(np.uint8([[[35, 230, 230]]]), cv2.COLOR_HSV2BGR)[0, 0]

    torso[:, 5:10] = fluorescent_yellow_bgr
    total, left, right = detector._hsv_coverage(torso)
    assert total > cfg.VEST_THRESH
    assert left > cfg.VEST_SIDE_THRESH
    assert right == 0.0
    assert not is_vest_evidence(total, left, right)

    torso[:, 90:95] = fluorescent_yellow_bgr
    total, left, right = detector._hsv_coverage(torso)
    assert is_vest_evidence(total, left, right)


def test_warning_color_is_red_in_bgr():
    blue, green, red = cfg.COLOR_WARN
    assert red > blue
    assert red > green
