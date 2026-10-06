"""Result files: one append-only JSONL per run, where the last record per task_id wins."""

import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from tqdm import tqdm

from . import RESULTS_DIR

RESPONSES_DIR = RESULTS_DIR / "responses"
JUDGMENTS_DIR = RESULTS_DIR / "judgments"


def run_id(model: str, variant: str, task_set: str) -> str:
    return f"{model}__{variant}__{task_set}"


def parse_run_id(rid: str) -> tuple[str, str, str]:
    model, variant, task_set = rid.split("__")
    return model, variant, task_set


def responses_path(rid: str) -> Path:
    return RESPONSES_DIR / f"{rid}.jsonl"


def judgments_path(judge: str, rid: str) -> Path:
    return JUDGMENTS_DIR / judge / f"{rid}.jsonl"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def load_latest(path: Path) -> dict[str, dict]:
    """task_id -> last record written for it."""
    out: dict[str, dict] = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line)
                    out[rec["task_id"]] = rec
    return out


def run_parallel(items: Iterable, work: Callable[[object], dict], out_path: Path,
                 workers: int, desc: str) -> None:
    """Run work(item) concurrently and append each returned record to out_path as it finishes."""
    items = list(items)
    if not items:
        print(f"{desc}: nothing to do")
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    with open(out_path, "a", encoding="utf-8") as f, ThreadPoolExecutor(workers) as pool:
        futures = [pool.submit(work, it) for it in items]
        for fut in tqdm(as_completed(futures), total=len(futures), desc=desc):
            rec = fut.result()
            with lock:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
