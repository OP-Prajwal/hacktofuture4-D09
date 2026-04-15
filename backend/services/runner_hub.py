"""
Runner Hub — WebSocket connection manager for live CI/CD terminal streaming.

Manages two types of WebSocket connections:
  1. Runners: Production servers / CI agents that stream logs
  2. Viewers: Dashboard browser tabs that watch logs in real-time
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket


@dataclass
class ProjectSession:
    """Tracks one active CI/CD session for a project."""
    workspace: str
    project: str
    runner: WebSocket | None = None
    viewers: list[WebSocket] = field(default_factory=list)
    logs: list[dict] = field(default_factory=list)
    status: str = "idle"  # idle | running | success | failed
    started_at: float | None = None
    exit_code: int | None = None


class RunnerConnectionManager:
    """
    Central hub that routes log lines from CI runners to dashboard viewers.
    """

    def __init__(self):
        self._sessions: dict[str, ProjectSession] = {}
        self._on_failure_callbacks: list = []

    def _key(self, workspace: str, project: str) -> str:
        return f"{workspace}/{project}"

    def get_session(self, workspace: str, project: str) -> ProjectSession:
        key = self._key(workspace, project)
        if key not in self._sessions:
            self._sessions[key] = ProjectSession(workspace=workspace, project=project)
        return self._sessions[key]

    def get_status(self, workspace: str, project: str) -> dict:
        session = self.get_session(workspace, project)
        return {
            "status": session.status,
            "exit_code": session.exit_code,
            "log_count": len(session.logs),
            "has_runner": session.runner is not None,
            "viewer_count": len(session.viewers),
        }

    # ── Runner connections ──

    async def connect_runner(self, websocket: WebSocket, workspace: str, project: str):
        await websocket.accept()
        session = self.get_session(workspace, project)
        session.runner = websocket
        session.status = "running"
        session.started_at = time.time()
        session.logs = []
        session.exit_code = None

        # Notify viewers that a runner connected
        await self._broadcast_to_viewers(session, {
            "type": "system",
            "message": f"Runner connected. CI/CD session started.",
            "timestamp": time.time()
        })

    async def disconnect_runner(self, workspace: str, project: str):
        session = self.get_session(workspace, project)
        session.runner = None
        if session.status == "running":
            session.status = "idle"

    async def handle_runner_message(self, workspace: str, project: str, data: dict):
        """Process an incoming message from a CI runner."""
        session = self.get_session(workspace, project)
        msg_type = data.get("type", "log")

        if msg_type == "log":
            log_entry = {
                "type": "log",
                "line": data.get("line", ""),
                "stream": data.get("stream", "stdout"),  # stdout or stderr
                "timestamp": time.time()
            }
            session.logs.append(log_entry)
            await self._broadcast_to_viewers(session, log_entry)

        elif msg_type == "exit":
            exit_code = data.get("code", 1)
            session.exit_code = exit_code
            session.status = "success" if exit_code == 0 else "failed"

            exit_msg = {
                "type": "exit",
                "code": exit_code,
                "status": session.status,
                "timestamp": time.time()
            }
            await self._broadcast_to_viewers(session, exit_msg)

            # Trigger auto-heal if failed
            if exit_code != 0:
                await self._on_ci_failure(session)

        elif msg_type == "step":
            # CI step progress (e.g., "Building...", "Testing...")
            step_msg = {
                "type": "step",
                "name": data.get("name", ""),
                "status": data.get("status", "running"),
                "timestamp": time.time()
            }
            await self._broadcast_to_viewers(session, step_msg)

    # ── Viewer connections ──

    async def connect_viewer(self, websocket: WebSocket, workspace: str, project: str):
        await websocket.accept()
        session = self.get_session(workspace, project)
        session.viewers.append(websocket)

        # Send session status
        await websocket.send_json({
            "type": "session_info",
            "status": session.status,
            "log_count": len(session.logs),
            "has_runner": session.runner is not None,
        })

        # Replay existing logs so viewer catches up
        for log in session.logs[-200:]:  # Last 200 lines
            try:
                await websocket.send_json(log)
            except Exception:
                break

    async def disconnect_viewer(self, websocket: WebSocket, workspace: str, project: str):
        session = self.get_session(workspace, project)
        if websocket in session.viewers:
            session.viewers.remove(websocket)

    # ── Internal ──

    async def _broadcast_to_viewers(self, session: ProjectSession, message: dict):
        dead: list[WebSocket] = []
        for viewer in session.viewers:
            try:
                await viewer.send_json(message)
            except Exception:
                dead.append(viewer)
        for d in dead:
            session.viewers.remove(d)

    async def _on_ci_failure(self, session: ProjectSession):
        """Called when CI exits with non-zero code. Triggers auto-healing."""
        # Collect last 50 log lines as context
        recent_logs = [entry.get("line", "") for entry in session.logs[-50:]]
        error_lines = [entry.get("line", "") for entry in session.logs if entry.get("stream") == "stderr"][-20:]

        failure_context = {
            "workspace": session.workspace,
            "project": session.project,
            "exit_code": session.exit_code,
            "recent_logs": recent_logs,
            "error_lines": error_lines,
        }

        # Notify viewers about auto-heal starting
        await self._broadcast_to_viewers(session, {
            "type": "auto_heal_start",
            "message": "Analyzing failure with AI...",
            "timestamp": time.time()
        })

        # Import here to avoid circular deps — the auto_healer will be called
        try:
            from services.auto_healer import trigger_auto_heal
            import threading

            def _run_heal():
                result = trigger_auto_heal(
                    workspace=session.workspace,
                    project=session.project,
                    logs=recent_logs,
                    error_lines=error_lines,
                    exit_code=session.exit_code or 1
                )
                # We can't await from a thread, so we store the result
                session.logs.append({
                    "type": "auto_heal_result",
                    "result": result,
                    "timestamp": time.time()
                })

            thread = threading.Thread(target=_run_heal, daemon=True)
            thread.start()
        except Exception as e:
            print(f"[RunnerHub] Auto-heal trigger failed: {e}")

    def on_failure_callback(self, callback):
        """Register a callback for CI failures."""
        self._on_failure_callbacks.append(callback)


# Singleton instance
runner_hub = RunnerConnectionManager()
