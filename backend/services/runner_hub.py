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
            # If it disconnected while still running, it violently crashed
            # without gracefully sending the exit packet.
            # We must trigger the incident analyzer!
            print(f"[RunnerHub] Runner violently disconnected without exit code! Triggering Orchestrator.")
            session.status = "failed"
            if session.exit_code is None:
                session.exit_code = 1
            await self._on_ci_failure(session)

    async def handle_runner_message(self, workspace: str, project: str, data: dict):
        """Process an incoming message from a CI runner."""
        session = self.get_session(workspace, project)
        msg_type = data.get("type", "log")
        
        print(f"[RunnerHub] Handling {msg_type} for {workspace}/{project}")

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
            print(f"[RunnerHub] Process exited with code {exit_code} for {workspace}/{project}")
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
            "exit_code": session.exit_code,
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
        """Called when process exits with non-zero code. Triggers incident analysis to inform the developer."""
        # Collect last 50 log lines as context
        recent_logs = [entry.get("line", "") for entry in session.logs[-50:]]
        error_lines = [entry.get("line", "") for entry in session.logs if entry.get("stream") == "stderr"][-20:]
        event_loop = asyncio.get_running_loop()

        # Notify viewers that incident analysis is starting
        await self._broadcast_to_viewers(session, {
            "type": "incident_analysis_start",
            "message": "🔍 Analyzing failure — generating incident report for developer...",
            "timestamp": time.time()
        })

        # Run the multi-agent orchestration to produce a forensic report
        try:
            from services.incident_analyzer import trigger_incident_analysis
            import threading

            def _run_analysis():
                print("session ",session)
                result = trigger_incident_analysis(
                    workspace=session.workspace,
                    project=session.project,
                    logs=recent_logs,
                    error_lines=error_lines,
                    exit_code=session.exit_code or 1
                )
                report_message = {
                    "type": "incident_report",
                    "incident_id": result.get("incident_id"),
                    "summary": result.get("summary"),
                    "status": result.get("status"),
                    "result": result,
                    "timestamp": time.time()
                }
                # Store the analysis result and push it live to connected viewers.
                session.logs.append(report_message)
                asyncio.run_coroutine_threadsafe(
                    self._broadcast_to_viewers(session, report_message),
                    event_loop
                )

            thread = threading.Thread(target=_run_analysis, daemon=True)
            thread.start()
        except Exception as e:
            print(f"[RunnerHub] Incident analysis trigger failed: {e}")

    def on_failure_callback(self, callback):
        """Register a callback for CI failures."""
        self._on_failure_callbacks.append(callback)


# Singleton instance
runner_hub = RunnerConnectionManager()
