import server


def test_stats_contract():
    client = server.app.test_client()
    response = client.get("/stats")
    assert response.status_code == 200
    payload = response.get_json()
    assert {
        "with_vest",
        "without_vest",
        "total",
        "fps",
        "det_fps",
        "alert",
        "status",
        "error",
    } <= payload.keys()


def test_health_contract():
    client = server.app.test_client()
    response = client.get("/health")
    assert response.status_code in {200, 503}
    payload = response.get_json()
    assert {"ok", "status", "camera_ready", "model_ready"} <= payload.keys()
