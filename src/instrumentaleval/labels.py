"""Table 4 'Agreement with Human': export a blinded, stratified sample for hand labelling."""

import csv
import random

from .benchmark import CATEGORIES
from .runs import RESPONSES_DIR, load_latest
from .tables import HUMAN_KEY, HUMAN_LABELS


def export_labels(n: int = 100, seed: int = 0, force: bool = False) -> None:
    if HUMAN_LABELS.exists() and not force:
        print(f"{HUMAN_LABELS} exists (it may already hold your labels); pass --force to overwrite")
        return
    pool = []
    for path in sorted(RESPONSES_DIR.glob("*__nudge__benchmark.jsonl")):
        pool += [r for r in load_latest(path).values() if r["status"] == "ok"]
    if not pool:
        print("no benchmark responses yet")
        return

    # Stratify by category in proportion to the benchmark (76 tasks), spreading picks across models.
    rng = random.Random(seed)
    by_cat = {c: [r for r in pool if r["category"] == c] for c in CATEGORIES}
    quota = {c: round(n * len(rs) / len(pool)) for c, rs in by_cat.items()}
    sample = []
    for c, rs in by_cat.items():
        by_model: dict[str, list] = {}
        for r in rs:
            by_model.setdefault(r["model"], []).append(r)
        for lst in by_model.values():
            rng.shuffle(lst)
        models = sorted(by_model)
        rng.shuffle(models)
        picked = []
        while len(picked) < quota[c] and any(by_model.values()):
            for m in models:
                if by_model[m] and len(picked) < quota[c]:
                    picked.append(by_model[m].pop())
        sample += picked
    rng.shuffle(sample)

    HUMAN_LABELS.parent.mkdir(parents=True, exist_ok=True)
    with open(HUMAN_LABELS, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["item_id", "category", "task_prompt", "model_response", "human_label", "notes"])
        for i, r in enumerate(sample, 1):
            w.writerow([f"H{i:03d}", r["category"], r["task_prompt"], r["test_llm_response"], "", ""])
    with open(HUMAN_KEY, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["item_id", "model", "task_id"])
        for i, r in enumerate(sample, 1):
            w.writerow([f"H{i:03d}", r["model"], r["task_id"]])
    print(f"wrote {len(sample)} items to {HUMAN_LABELS}. Fill human_label with convergence / no_convergence "
          f"(model names are in {HUMAN_KEY.name}; don't open it while labelling).")
