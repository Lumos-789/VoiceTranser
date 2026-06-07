"""Local HTTP server for toggle-based voice input (replaces pynput hotkey)."""

from __future__ import annotations

import json
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from voicetranser.config import Config
    from voicetranser.recorder import Recorder
    from voicetranser.status import StatusDisplay

# States
_IDLE = "idle"
_RECORDING = "recording"
_PROCESSING = "processing"


class _Context:
    """Shared mutable state across all handler instances."""

    __slots__ = ("recorder", "status", "config", "state", "lock")

    def __init__(self) -> None:
        self.recorder: Recorder | None = None
        self.status: StatusDisplay | None = None
        self.config: Config | None = None
        self.state: str = _IDLE
        self.lock: threading.Lock = threading.Lock()


# Single shared context — handler instances access via class attribute.
_ctx = _Context()


class _Handler(BaseHTTPRequestHandler):
    """Handles /toggle and /status requests."""

    def do_GET(self) -> None:
        if self.path == "/toggle":
            self._handle_toggle()
        elif self.path == "/start":
            self._handle_start()
        elif self.path == "/stop":
            self._handle_stop()
        elif self.path == "/status":
            self._handle_status()
        else:
            self._send(404, {"error": "not found"})

    def _handle_toggle(self) -> None:
        with _ctx.lock:
            if _ctx.state == _IDLE:
                _ctx.state = _RECORDING
                _ctx.recorder.start()
                _ctx.status.recording()
                self._send(200, {"status": _RECORDING})
            elif _ctx.state == _RECORDING:
                audio_data = _ctx.recorder.stop()
                if audio_data is None:
                    _ctx.state = _IDLE
                    _ctx.status.clear()
                    sys.stderr.write("[Recording too short]\n")
                    self._send(200, {"status": _IDLE, "message": "too short"})
                    return
                _ctx.state = _PROCESSING
                self._send(200, {"status": _PROCESSING})
                # Process in background thread
                threading.Thread(
                    target=self._process, args=(audio_data,), daemon=True
                ).start()
            else:
                # Already processing — reject
                self._send(409, {"status": _ctx.state, "message": "busy"})

    def _handle_status(self) -> None:
        with _ctx.lock:
            self._send(200, {"status": _ctx.state})

    def _handle_start(self) -> None:
        """Begin recording (for press-and-hold via external hotkey tool)."""
        with _ctx.lock:
            if _ctx.state != _IDLE:
                self._send(409, {"status": _ctx.state, "message": "busy"})
                return
            _ctx.state = _RECORDING
            _ctx.recorder.start()
            _ctx.status.recording()
            self._send(200, {"status": _RECORDING})

    def _handle_stop(self) -> None:
        """Stop recording and process (for press-and-hold via external hotkey tool)."""
        with _ctx.lock:
            if _ctx.state != _RECORDING:
                self._send(409, {"status": _ctx.state, "message": "not recording"})
                return
            audio_data = _ctx.recorder.stop()
            if audio_data is None:
                _ctx.state = _IDLE
                _ctx.status.clear()
                sys.stderr.write("[Recording too short]\n")
                self._send(200, {"status": _IDLE, "message": "too short"})
                return
            _ctx.state = _PROCESSING
            self._send(200, {"status": _PROCESSING})
            threading.Thread(
                target=self._process, args=(audio_data,), daemon=True
            ).start()

    def _process(self, audio_data: bytes) -> None:
        """Worker: transcribe → paste, then return to idle."""
        from voicetranser.__main__ import process_audio

        try:
            process_audio(audio_data, _ctx.config, auto_paste=True, status=_ctx.status)
        except Exception:
            import traceback
            traceback.print_exc()
        finally:
            with _ctx.lock:
                _ctx.state = _IDLE

    def _send(self, code: int, body: dict) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def log_message(self, format: str, *args: object) -> None:
        # Suppress default access logs
        pass


class VoiceServer:
    """HTTP server that manages voice input via toggle endpoint."""

    def __init__(
        self,
        config: Config,
        recorder: Recorder,
        status: StatusDisplay,
        host: str = "127.0.0.1",
        port: int = 9876,
    ) -> None:
        _ctx.recorder = recorder
        _ctx.status = status
        _ctx.config = config
        _ctx.state = _IDLE
        self._host = host
        self._port = port

    def start(self) -> None:
        """Start the HTTP server (blocks the calling thread)."""
        server = HTTPServer((self._host, self._port), _Handler)
        sys.stderr.write(
            f"[VoiceTranser] HTTP server listening on {self._host}:{self._port}\n"
            "  GET /start   — start recording\n"
            "  GET /stop    — stop recording & process\n"
            "  GET /toggle  — toggle start/stop\n"
            "  GET /status  — current state\n"
        )
        server.serve_forever()
