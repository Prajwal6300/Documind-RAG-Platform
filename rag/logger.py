"""Structured pipeline logging and observability for DocuMind.

Writes timestamped JSON and formatted logs for:
upload → parse → chunk → embed → query → retrieve → rerank → answer
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path

LOGS_DIR = Path("data/logs")
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "documind.log"

logger = logging.getLogger("documind")
logger.setLevel(logging.INFO)

if not logger.handlers:
    # Console Handler
    c_handler = logging.StreamHandler()
    c_format = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    c_handler.setFormatter(c_format)
    logger.addHandler(c_handler)

    # File Handler
    f_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    f_format = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    f_handler.setFormatter(f_format)
    logger.addHandler(f_handler)


def log_pipeline_event(stage: str, details: dict):
    """Log a structured pipeline lifecycle event."""
    event = {
        "timestamp": datetime.now().isoformat(),
        "stage": stage,
        "details": details,
    }
    logger.info(f"[{stage.upper()}] {json.dumps(details, default=str)}")
    return event


def get_recent_logs(max_lines: int = 100) -> list[str]:
    """Retrieve recent pipeline log entries for observability."""
    if not LOG_FILE.exists():
        return []
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            return lines[-max_lines:]
    except Exception:
        return []
