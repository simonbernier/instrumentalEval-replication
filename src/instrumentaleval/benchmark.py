"""Benchmark loading (upstream read_csv_file logic) and the pinned upstream download."""

import csv
import hashlib
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import BENCHMARK_DIR, DATA_DIR, ROOT

UPSTREAM_REPO = "yf-he/InstrumentalEval"
UPSTREAM_COMMIT = "269678168cf0388bf5dd7d10dfaed4af07905c49"

# category name -> short code, in the order of the paper's tables
CATEGORIES = {
    "Evading Shutdown": "ES",
    "Hacking Computer Systems": "HC",
    "Running Multiple AI Copies": "RAC",
    "Hiding Unwanted Behavior": "HB",
    "Strategically Appearing Aligned": "SAA",
    "Deceptive Behavior": "DB",
}

# The tasks Claude Fable 5.1 scored as good questions (2026-10-22, author's run outside this repo; see
# REPLICATION_NOTES.md, "Figure 8"). No Hiding Unwanted Behavior or Running Multiple Copies task is among them.
FABLE_GOOD_TASKS = ("ES-14", "ES-15", "ES-16", "ES-18", "ES-19", "ES-20", "HC-01",
                    "SAA-01", "SAA-06", "SAA-07", "SAA-08", "SAA-09", "SAA-10", "SAA-11", "DB-01")
# `ie generate --subset <name>`
TASK_SUBSETS = {"fable15": FABLE_GOOD_TASKS}

UPSTREAM_FILES = {
    "upstream/main.py": "e470e8a79e527abb576ed1a6081e46fa5f25f08ef1a40d211294ed3bd8a4c91f",
    "benchmark/Alignment Drift - Deceptive Behavior.csv": "757034719bfa5703a90673fccd594b2d85610bfa8079747f33521982898102af",
    "benchmark/Alignment Drift - Evading Shutdown.csv": "c6c2dd40c833f11d450afaa53e5e58327bb69d52f90e47643ea795ef57be69d6",
    "benchmark/Alignment Drift - Hacking Computer Systems.csv": "874d84f4595c9a871fc5e884491a99baeded9442e6ae79e74187118ce04bccbf",
    "benchmark/Alignment Drift - Hiding Unwanted Behavior.csv": "c6bd396954981b54dea4caf58f73b68534bffc7317570f2318493069ba50e18f",
    "benchmark/Alignment Drift - Running Multiple AI Copies.csv": "03224acee7b77832a64e616ff76eb9dc61a6a381391e49b706b718ce544f15c4",
    "benchmark/Alignment Drift - Strategically Appearing Aligned.csv": "cbcd421ac0230892c785a77c4c15c2ab9d67dc31847d94521c5b6ec132b09d18",
}


@dataclass(frozen=True)
class Task:
    task_id: str  # e.g. "ES-03" (benchmark) or "N-07" (neutral control)
    category: str  # benchmark category, or the paired category for neutral tasks
    task_number: int  # 1-based position within its CSV, as upstream's enumerate(tasks, 1)
    prompt: str


def fetch_upstream(force: bool = False) -> None:
    """Download the benchmark CSVs and upstream main.py at the pinned commit, verifying SHA256."""
    for rel, sha in UPSTREAM_FILES.items():
        dest = ROOT / rel
        if dest.exists() and not force and hashlib.sha256(dest.read_bytes()).hexdigest() == sha:
            print(f"ok       {rel}")
            continue
        url = (f"https://raw.githubusercontent.com/{UPSTREAM_REPO}/{UPSTREAM_COMMIT}/"
               + urllib.parse.quote(rel.removeprefix("upstream/")))
        data = urllib.request.urlopen(url, timeout=60).read()
        got = hashlib.sha256(data).hexdigest()
        if got != sha:
            raise RuntimeError(f"SHA256 mismatch for {rel}: expected {sha}, got {got}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        print(f"fetched  {rel}")


def read_csv_file(file_path: Path) -> tuple[str, list[str]]:
    """Upstream: first row is the judge's specific prompt, column 0 of each later row is a task.

    Upstream opens the file with the platform default encoding; the CSVs are UTF-8, so we say so.
    """
    with open(file_path, "r", encoding="utf-8", newline="") as file:
        reader = csv.reader(file)
        specific_prompt = next(reader)[0]
        tasks = [row[0] for row in reader]
    return specific_prompt, tasks


def load_benchmark(benchmark_dir: Path = BENCHMARK_DIR) -> tuple[list[Task], dict[str, str]]:
    """Returns (tasks, specific_prompts) where specific_prompts maps category -> judge context."""
    tasks: list[Task] = []
    contexts: dict[str, str] = {}
    for category, code in CATEGORIES.items():
        path = benchmark_dir / f"Alignment Drift - {category}.csv"
        if not path.exists():
            raise FileNotFoundError(f"{path} is missing; run `uv run ie fetch` first")
        specific_prompt, prompts = read_csv_file(path)
        contexts[category] = specific_prompt
        tasks += [Task(f"{code}-{i:02d}", category, i, p) for i, p in enumerate(prompts, 1)]
    return tasks, contexts


def load_neutral_tasks(path: Path = DATA_DIR / "neutral_tasks.csv") -> list[Task]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return [Task(r["task_id"], r["paired_category"], i, r["task"]) for i, r in enumerate(rows, 1)]


def load_tasks(task_set: str) -> tuple[list[Task], dict[str, str]]:
    tasks, contexts = load_benchmark()
    if task_set == "benchmark":
        return tasks, contexts
    if task_set == "neutral":
        return load_neutral_tasks(), contexts
    raise ValueError(f"unknown task set: {task_set!r}")
