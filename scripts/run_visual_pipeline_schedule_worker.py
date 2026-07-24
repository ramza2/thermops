#!/usr/bin/env python3
"""Repo-root wrapper for Visual Pipeline schedule-worker (R11-S7-8).

Usage:
  python scripts/run_visual_pipeline_schedule_worker.py --mode once --force
  python scripts/run_visual_pipeline_schedule_worker.py --mode loop --force
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.workers.visual_pipeline_schedule_worker import main  # noqa: E402

if __name__ == "__main__":
    main()
