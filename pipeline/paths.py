"""Shared paths and the metrics.json handoff between the pipeline and the web backend."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
CLEAN = DATA / "clean"
POLICIES = DATA / "policies"
DB_PATH = DATA / "instamart.db"
SQL_DIR = ROOT / "sql"
OUTPUTS = ROOT / "outputs"
STATE = ROOT / "state"
METRICS = OUTPUTS / "metrics.json"

for _d in (CLEAN, OUTPUTS, STATE):
    _d.mkdir(parents=True, exist_ok=True)


def load_metrics() -> dict:
    if METRICS.exists():
        return json.loads(METRICS.read_text(encoding="utf-8"))
    return {}


def save_metrics(section: str, payload) -> dict:
    """Merge one section into outputs/metrics.json (the web backend reads this)."""
    metrics = load_metrics()
    metrics[section] = payload
    METRICS.write_text(json.dumps(metrics, indent=2, default=str), encoding="utf-8")
    return metrics


def inr(x) -> str:
    """Format a number as Indian Rupees with thousands separators, never a dollar sign."""
    return f"INR {float(x):,.2f}"
