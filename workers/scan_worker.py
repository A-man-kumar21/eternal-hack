"""e-Abhilekh ingest worker: DB-polling background process (no Celery/Redis).

This is a deliberate simplification for the hackathon prototype: the API
stages uploads and inserts a scan_jobs row; this process polls for pending
jobs and runs the full ingest pipeline (validation -> hash -> AV ->
envelope encryption -> object storage).

Run:  python workers/scan_worker.py [--once] [--interval 5]
"""
from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _candidate in (ROOT / "apps" / "api", Path("/srv/api")):
    if (_candidate / "app").exists():
        sys.path.insert(0, str(_candidate))
        break

from app.db import get_session_factory  # noqa: E402
from app.services.ingest import process_pending  # noqa: E402
from app.storage import get_storage  # noqa: E402


def run_once() -> int:
    db = get_session_factory()()
    try:
        return process_pending(db, get_storage())
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="process pending jobs once and exit")
    parser.add_argument("--interval", type=int, default=5, help="poll interval in seconds")
    args = parser.parse_args()

    if args.once:
        n = run_once()
        print(f"worker: processed {n} job(s)")
        return

    print(f"worker: polling every {args.interval}s (Ctrl+C to stop)")
    while True:
        try:
            n = run_once()
            if n:
                print(f"worker: processed {n} job(s)")
        except Exception:
            traceback.print_exc()
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
