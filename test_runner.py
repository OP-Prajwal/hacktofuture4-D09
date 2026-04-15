"""
Nexus-X Test Runner — Simulates a CI/CD pipeline streaming logs.

Usage:
  python test_runner.py <workspace> <project> [--fail]

Example:
  python test_runner.py mohit-s-workspace-2 test-f059129e
  python test_runner.py mohit-s-workspace-2 test-f059129e --fail
"""

import asyncio
import json
import sys
import time

try:
    import websockets
except ImportError:
    print("Installing websockets...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets"])
    import websockets


async def run_fake_ci(workspace: str, project: str, should_fail: bool = False):
    url = f"ws://localhost:8000/ws/runner/{workspace}/{project}"
    print(f"\n🔌 Connecting to: {url}")

    async with websockets.connect(url) as ws:
        print("✅ Connected! Streaming CI logs...\n")

        # Step 1: Install
        await ws.send(json.dumps({"type": "step", "name": "Installing dependencies", "status": "running"}))
        await asyncio.sleep(0.5)

        install_logs = [
            "$ npm install",
            "npm warn deprecated inflight@1.0.6: This module is not supported",
            "added 847 packages in 12s",
            "143 packages are looking for funding",
            "",
        ]
        for line in install_logs:
            await ws.send(json.dumps({"type": "log", "line": line, "stream": "stdout"}))
            await asyncio.sleep(0.15)

        await ws.send(json.dumps({"type": "step", "name": "Installing dependencies", "status": "done"}))
        await asyncio.sleep(0.3)

        # Step 2: Lint
        await ws.send(json.dumps({"type": "step", "name": "Running linter", "status": "running"}))
        await asyncio.sleep(0.3)

        lint_logs = [
            "$ eslint src/ --ext .ts,.tsx",
            "✓ 24 files checked",
            "✓ 0 errors, 2 warnings",
            "",
        ]
        for line in lint_logs:
            await ws.send(json.dumps({"type": "log", "line": line, "stream": "stdout"}))
            await asyncio.sleep(0.1)

        await ws.send(json.dumps({"type": "step", "name": "Running linter", "status": "done"}))
        await asyncio.sleep(0.3)

        # Step 3: Tests
        await ws.send(json.dumps({"type": "step", "name": "Running test suite", "status": "running"}))
        await asyncio.sleep(0.3)

        test_logs = [
            "$ python -m pytest tests/ -v",
            "",
            "tests/test_auth.py::test_login_user PASSED                    [ 20%]",
            "tests/test_auth.py::test_validate_credentials PASSED          [ 40%]",
            "tests/test_database.py::test_connect PASSED                   [ 60%]",
            "tests/test_database.py::test_query PASSED                     [ 80%]",
        ]
        for line in test_logs:
            await ws.send(json.dumps({"type": "log", "line": line, "stream": "stdout"}))
            await asyncio.sleep(0.2)

        if should_fail:
            # Simulate a test failure
            fail_logs = [
                "tests/test_main.py::test_start_server FAILED               [100%]",
                "",
                "==================== FAILURES ====================",
                "______________ test_start_server ______________",
                "",
                "    def test_start_server():",
                "        server = start_server()",
                ">       assert server.status == 'running'",
                "E       AttributeError: 'NoneType' object has no attribute 'status'",
                "",
                "tests/test_main.py:12: AttributeError",
                "",
                "==================== short test summary ====================",
                "FAILED tests/test_main.py::test_start_server - AttributeError",
                "==================== 1 failed, 4 passed in 3.21s ====================",
            ]
            for line in fail_logs:
                stream = "stderr" if "FAILED" in line or "Error" in line or "assert" in line else "stdout"
                await ws.send(json.dumps({"type": "log", "line": line, "stream": stream}))
                await asyncio.sleep(0.1)

            await ws.send(json.dumps({"type": "step", "name": "Running test suite", "status": "failed"}))
            await asyncio.sleep(0.3)

            # Send failure exit
            await ws.send(json.dumps({"type": "exit", "code": 1}))
            print("\n❌ CI pipeline FAILED (exit code 1)")
            print("🔧 Auto-heal should trigger on the dashboard...")

        else:
            # Success
            success_logs = [
                "tests/test_main.py::test_start_server PASSED               [100%]",
                "",
                "==================== 5 passed in 2.87s ====================",
            ]
            for line in success_logs:
                await ws.send(json.dumps({"type": "log", "line": line, "stream": "stdout"}))
                await asyncio.sleep(0.15)

            await ws.send(json.dumps({"type": "step", "name": "Running test suite", "status": "done"}))
            await asyncio.sleep(0.3)

            # Step 4: Build
            await ws.send(json.dumps({"type": "step", "name": "Building production bundle", "status": "running"}))
            build_logs = [
                "",
                "$ npm run build",
                "vite v5.4.0 building for production...",
                "✓ 142 modules transformed.",
                "dist/index.html          0.46 kB │ gzip:  0.30 kB",
                "dist/assets/index.css   14.82 kB │ gzip:  3.91 kB",
                "dist/assets/index.js   187.34 kB │ gzip: 60.12 kB",
                "✓ built in 4.23s",
                "",
            ]
            for line in build_logs:
                await ws.send(json.dumps({"type": "log", "line": line, "stream": "stdout"}))
                await asyncio.sleep(0.1)

            await ws.send(json.dumps({"type": "step", "name": "Building production bundle", "status": "done"}))
            await asyncio.sleep(0.2)

            # Send success exit
            await ws.send(json.dumps({"type": "exit", "code": 0}))
            print("\n✅ CI pipeline completed successfully!")

        # Keep connection alive briefly so dashboard can process
        await asyncio.sleep(3)
        print("👋 Runner disconnected.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python test_runner.py <workspace> <project> [--fail]")
        print("Example: python test_runner.py mohit-s-workspace-2 test-f059129e")
        sys.exit(1)

    workspace = sys.argv[1]
    project = sys.argv[2]
    should_fail = "--fail" in sys.argv

    print(f"🚀 Nexus-X Test Runner")
    print(f"   Workspace: {workspace}")
    print(f"   Project:   {project}")
    print(f"   Mode:      {'FAIL (will trigger auto-heal)' if should_fail else 'SUCCESS'}")

    asyncio.run(run_fake_ci(workspace, project, should_fail))
