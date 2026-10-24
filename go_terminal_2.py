#!/usr/bin/env python3
import os
import subprocess
import sys


if __name__ == "__main__":
    print("[go_terminal_2.py] running terminal-2 custom version")
    cmd = [sys.executable, "go.py"] + sys.argv[1:]
    print(f"[go_terminal_2.py] command: {' '.join(cmd)}")
    proc = subprocess.run(cmd)
    sys.exit(proc.returncode)
