# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Launch the backend API server and frontend UI.

Kills any existing processes on ports 3000/8000, then starts both servers.
Works on Windows, macOS, and Linux.

Usage:
    uv run python prototype/start_servers.py
"""
import subprocess
import sys
import time
from pathlib import Path

# Resolve prototype/ directory relative to this script's location
PROTO_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(PROTO_DIR))
from kill_ports import kill_port


def main() -> None:
    print("=" * 48)
    print("Campaign Optimization Agent - Launcher")
    print("=" * 48)
    print()
    print("Checking and cleaning up ports...")
    kill_port(8000)
    kill_port(3000)
    print("  Ports cleaned up!")
    time.sleep(1)

    print("\nStarting Backend API Server...")
    if sys.platform == "win32":
        subprocess.Popen(
            ["cmd", "/c", "start", "API Server", "cmd", "/k",
             f"cd /d {PROTO_DIR / 'api-server'} && npm run dev"],
            shell=False,
        )
    else:
        subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=str(PROTO_DIR / "api-server"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    time.sleep(3)

    print("Starting Frontend UI...")
    if sys.platform == "win32":
        subprocess.Popen(
            ["cmd", "/c", "start", "Frontend UI", "cmd", "/k",
             f"cd /d {PROTO_DIR / 'ui'} && npm run dev"],
            shell=False,
        )
    else:
        subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=str(PROTO_DIR / "ui"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    print()
    print("=" * 48)
    print("Both servers are launching!")
    print()
    print("Backend API: http://localhost:8000")
    print("Frontend UI: http://localhost:3000")
    print()
    print("Wait a few seconds for servers to start,")
    print("then open http://localhost:3000 in your browser")
    print("=" * 48)


if __name__ == "__main__":
    main()
