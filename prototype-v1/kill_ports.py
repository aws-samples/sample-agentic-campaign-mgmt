# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Kill processes listening on ports 3000 (frontend) and 8000 (backend).

Works on Windows, macOS, and Linux.

Usage:
    uv run python prototype/kill_ports.py
"""
import subprocess
import sys


def kill_port(port: int) -> None:
    if sys.platform == "win32":
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True,
        )
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                pid = line.strip().split()[-1]
                print(f"  Killing process on port {port} (PID: {pid})")
                subprocess.run(["taskkill", "/PID", pid, "/F"],
                               capture_output=True)
                return
    else:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True,
        )
        pids = result.stdout.strip()
        if pids:
            for pid in pids.splitlines():
                print(f"  Killing process on port {port} (PID: {pid})")
                subprocess.run(["kill", "-9", pid], capture_output=True)
            return

    print(f"  No process found on port {port}")


def main() -> None:
    print("Cleaning up ports 3000 and 8000...\n")
    kill_port(8000)
    kill_port(3000)
    print("\nDone! Ports 3000 and 8000 are now free.")


if __name__ == "__main__":
    main()
