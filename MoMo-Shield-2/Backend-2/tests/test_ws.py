import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_websocket_telemetry_connect():
    with client.websocket_connect("/api/v1/ws/telemetry") as ws:
        ws.send_text("ping")
