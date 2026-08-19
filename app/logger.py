"""Structured JSON logger for Wi-Fi Helper failure diagnostics."""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Optional
from app.probe import ProbeResult

# Configure base logger to stdout
logger = logging.getLogger("wifi_helper")
logger.setLevel(logging.INFO)

# Ensure handler is attached only once
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)


def log_failure(
    probe_result: ProbeResult,
    client_ip: str,
    room: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> dict:
    """
    Log a structured JSON event for a MikroTik probe failure.
    
    Successful requests MUST NOT generate failure logs or alerts.
    Only failures are recorded with structured metadata.
    """
    event_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": "ERROR",
        "event": "mikrotik_probe_failed",
        "client_ip": client_ip,
        "room": room,
        "error_type": probe_result.error_type,
        "error_message": probe_result.error_message,
        "status_code": probe_result.status_code,
        "probe_duration_ms": probe_result.duration_ms,
        "target_url": probe_result.target_url,
        "user_agent": user_agent or "unknown",
    }

    # Output formatted JSON line
    logger.error(json.dumps(event_data, ensure_ascii=False))
    return event_data
