"""
WebSocket server that broadcasts game state payloads to connected clients
(the Chrome extension content script).

Usage:
    from backend.ws_server import WSServer

    server = WSServer(port=8765)
    server.start()          # starts in a background thread
    server.broadcast(data)  # send dict to all connected clients
    server.stop()           # clean shutdown
"""

import asyncio
import json
import threading
import websockets


class WSServer:
    def __init__(self, port: int = 8765):
        self.port = port
        self._clients: set = set()
        self._loop: asyncio.AbstractEventLoop = None
        self._thread: threading.Thread = None
        self._server = None
        self._last_message: str = None  # sent to new clients on connect

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        """Start the WebSocket server in a daemon background thread."""
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def broadcast(self, data: dict):
        """
        Send a JSON payload to all currently connected extension clients.
        Thread-safe — can be called from the main Selenium game loop.
        """
        if self._loop is None:
            return
        message = json.dumps(data)
        self._last_message = message
        if not self._clients:
            return
        asyncio.run_coroutine_threadsafe(self._broadcast_async(message), self._loop)

    def stop(self):
        """Signal the event loop to shut down."""
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._serve())

    async def _serve(self):
        try:
            async with websockets.serve(self._handler, "localhost", self.port):
                print(f"[PAI] WebSocket server listening on ws://localhost:{self.port}")
                await asyncio.Future()  # run forever
        except OSError as e:
            print(f"[PAI] ERROR: Port {self.port} is already in use. "
                  f"Set a different port with: PAI_WS_PORT=8766 python main.py")
            raise

    async def _handler(self, websocket):
        self._clients.add(websocket)
        # Send current state immediately so new connections don't wait for next change
        if self._last_message:
            try:
                await websocket.send(self._last_message)
            except websockets.exceptions.ConnectionClosed:
                self._clients.discard(websocket)
                return
        try:
            async for _ in websocket:
                pass
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._clients.discard(websocket)

    async def _broadcast_async(self, message: str):
        if not self._clients:
            return
        # Copy to avoid mutation during iteration
        for ws in set(self._clients):
            try:
                await ws.send(message)
            except websockets.exceptions.ConnectionClosed:
                self._clients.discard(ws)
