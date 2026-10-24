#!/usr/bin/env python3
import argparse
import os
import sys
import time


def parse_args():
    parser = argparse.ArgumentParser(description="Reusable terminal worker for Render-based terminal dashboard")
    parser.add_argument("-s", "--target-ip", dest="target_ip", required=True, help="Target IP address")
    parser.add_argument("-t", "--threads", dest="threads", type=int, default=1, help="Thread count")
    return parser.parse_args()


def main():
    args = parse_args()
    print(f"[go.py] Starting worker for target IP: {args.target_ip}")
    print(f"[go.py] Threads: {args.threads}")
    print("[go.py] Edit this file in GitHub to change the logic for your own attack / automation workflow.")

    for i in range(1, max(2, args.threads + 1)):
        print(f"[go.py] worker {i}/{args.threads} active")
        time.sleep(0.5)

    print("[go.py] Finished.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[go.py] interrupted by user")
        sys.exit(130)
