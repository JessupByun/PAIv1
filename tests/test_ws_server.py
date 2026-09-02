import asyncio
import json
import time
import pytest
import websockets
from backend.ws_server import WSServer

TEST_PORT = 8766  # use a different port to avoid conflicts with a live server


@pytest.fixture(scope="module")
def server():
    s = WSServer(port=TEST_PORT)
    s.start()
    time.sleep(0.5)  # give the event loop a moment to start
    yield s
    s.stop()


def test_server_starts(server):
    """Server fixture starts without raising."""
    assert server._loop is not None


def test_client_connects(server):
    """A client can establish a WebSocket connection."""
    async def _connect():
        async with websockets.connect(f"ws://localhost:{TEST_PORT}") as ws:
            # Connection succeeded if we reach here without exception
            assert ws is not None

    asyncio.run(_connect())


def test_broadcast_received(server):
    """A broadcast payload is received by a connected client."""
    payload = {"test": True, "value": 42}
    received = []

    async def _run():
        async with websockets.connect(f"ws://localhost:{TEST_PORT}") as ws:
            # Give server a moment to register the client
            await asyncio.sleep(0.1)
            server.broadcast(payload)
            await asyncio.sleep(0.3)
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                received.append(json.loads(msg))
            except asyncio.TimeoutError:
                pass

    asyncio.run(_run())
    assert len(received) == 1
    assert received[0]["test"] is True
    assert received[0]["value"] == 42


def test_broadcast_with_no_clients_does_not_crash(server):
    """broadcast() with no connected clients should not raise."""
    try:
        server.broadcast({"safe": True})
    except Exception as e:
        pytest.fail(f"broadcast() raised unexpectedly: {e}")
