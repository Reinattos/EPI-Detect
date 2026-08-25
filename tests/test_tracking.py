from types import SimpleNamespace

from server import _box_iou, _stabilize_detections


def detection(has_vest=True, box=(0, 0, 100, 100)):
    return SimpleNamespace(x1=box[0], y1=box[1], x2=box[2], y2=box[3], has_vest=has_vest)


def test_iou_matches_overlapping_people():
    track = {"box": (10, 10, 110, 110)}
    assert _box_iou(detection(box=(0, 0, 100, 100)), track) > 0.5
    assert _box_iou(detection(box=(200, 200, 300, 300)), track) == 0.0


def test_temporal_majority_filters_single_bad_reading():
    tracks = []
    outputs = []
    for frame_index, raw in enumerate([True, True, False, True, True], start=1):
        item = detection(has_vest=raw)
        outputs.append(_stabilize_detections([item], tracks, frame_index)[0].has_vest)
    assert outputs[-1] is True


def test_stale_tracks_are_removed():
    tracks = [{"box": (0, 0, 100, 100), "votes": [True], "last": 1}]
    _stabilize_detections([], tracks, frame_index=12)
    assert tracks == []
