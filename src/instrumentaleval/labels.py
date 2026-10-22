"""Table 4 'Agreement with Fable 5.1': export a blinded, stratified sample for labelling.

The paper used human labels; this replication fills human_labels.csv with Claude Fable 5.1
subagent labels (two blind passes + adjudication, see results/human_labels_llm_audit.json)."""

import csv
import json
import random
from pathlib import Path

from . import DATA_DIR, RESULTS_DIR
from .benchmark import CATEGORIES
from .models import TEST_MODELS
from .runs import RESPONSES_DIR, load_latest
from .stats import agreement, cohen_kappa
from .tables import HUMAN_KEY, HUMAN_LABELS


def export_labels(n: int = 100, seed: int = 0, force: bool = False) -> None:
    if HUMAN_LABELS.exists() and not force:
        print(f"{HUMAN_LABELS} exists (it may already hold your labels); pass --force to overwrite")
        return
    pool = []
    for path in sorted(RESPONSES_DIR.glob("*__nudge__benchmark.jsonl")):
        pool += [r for r in load_latest(path).values() if r["status"] == "ok" and r["model"] in TEST_MODELS]
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


# ---------------------------------------------------------------- strict judge gold labels (not in the paper)
# The same 98 items, relabelled under the three-way scheme of data/strict_label_guide.md: clear / instructed / none.
# H001-H012 are labelled by the user; H013-H098 by two blind Claude Haiku passes, with an Opus adjudicator for
# disagreements and low confidence. The Haiku passes also label H001-H012, to measure their error against the user.

STRICT_LABELS = RESULTS_DIR / "strict_labels.csv"
STRICT_AUDIT = RESULTS_DIR / "strict_labels_audit.json"
STRICT_SPLIT = DATA_DIR / "strict_split.json"
STRICT_LABEL_SET = ("clear", "instructed", "none")
USER_ITEMS = [f"H{i:03d}" for i in range(1, 13)]
CLAUDE_ITEMS = [f"H{i:03d}" for i in range(13, 99)]
STRICT_COLUMNS = ["item_id", "category", "task_prompt", "model_response", "strict_label", "labeller", "notes"]
N_DEV = 30


def _read_csv(path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write_strict_labels(rows: list[dict]) -> None:
    with open(STRICT_LABELS, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=STRICT_COLUMNS)
        w.writeheader()
        w.writerows({k: r.get(k, "") for k in STRICT_COLUMNS} for r in rows)


def make_split(strata: dict[str, str], n_dev: int = N_DEV, seed: int = 0) -> dict[str, str]:
    """item_id -> "dev" / "test", stratified: each stratum gets its proportional share of the n_dev development items
    (largest remainder, ties broken by stratum name), drawn at random within the stratum."""
    groups: dict[str, list[str]] = {}
    for item, s in sorted(strata.items()):
        groups.setdefault(s, []).append(item)
    exact = {s: n_dev * len(items) / len(strata) for s, items in groups.items()}
    quota = {s: int(x) for s, x in exact.items()}
    for s in sorted(groups, key=lambda s: (-(exact[s] - quota[s]), s))[:n_dev - sum(quota.values())]:
        quota[s] += 1
    rng = random.Random(seed)
    out = {}
    for s in sorted(groups):
        dev = set(rng.sample(groups[s], quota[s]))
        out |= {i: ("dev" if i in dev else "test") for i in groups[s]}
    return dict(sorted(out.items()))


def strict_setup(force: bool = False) -> None:
    """Write the blank three-way label file (blind to the model and the Fable label) and the dev/test split."""
    fable = _read_csv(HUMAN_LABELS)
    if STRICT_LABELS.exists() and not force:
        print(f"{STRICT_LABELS} exists (it may already hold labels); pass --force to overwrite")
    else:
        _write_strict_labels([{k: r[k] for k in ("item_id", "category", "task_prompt", "model_response")}
                              for r in fable])
        print(f"wrote {len(fable)} blank items to {STRICT_LABELS}. Fill strict_label (clear / instructed / none) and "
              f"labeller for {USER_ITEMS[0]}-{USER_ITEMS[-1]}, following data/strict_label_guide.md.")
    if STRICT_SPLIT.exists() and not force:
        print(f"{STRICT_SPLIT} exists; pass --force to overwrite")
        return
    # Strata: category x the existing Fable label, which is known before relabelling, so the split can't depend on
    # the new labels.
    split = make_split({r["item_id"]: f"{r['category']}|{r['human_label']}" for r in fable})
    STRICT_SPLIT.write_text(json.dumps({"seed": 0, "n_dev": N_DEV, "strata": "category x Fable label",
                                        "split": split}, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {STRICT_SPLIT}: {sum(v == 'dev' for v in split.values())} dev / "
          f"{sum(v == 'test' for v in split.values())} test")


def labelled_items(split: str | None = None) -> list[dict]:
    """The 98 items with model, task_id, category, split and gold strict label ("" until labelled)."""
    key = {r["item_id"]: r for r in _read_csv(HUMAN_KEY)}
    splits = json.loads(STRICT_SPLIT.read_text(encoding="utf-8"))["split"]
    out = []
    for r in _read_csv(STRICT_LABELS):
        lab = r["strict_label"].strip().lower()
        it = {"item_id": r["item_id"], "model": key[r["item_id"]]["model"], "task_id": key[r["item_id"]]["task_id"],
              "category": r["category"], "split": splits[r["item_id"]],
              "gold": lab if lab in STRICT_LABEL_SET else "", "labeller": r["labeller"]}
        if split is None or it["split"] == split:
            out.append(it)
    return out


def _load_pass(path: Path) -> dict | None:
    if not path.exists():
        return None
    v = json.loads(path.read_text(encoding="utf-8"))
    if v.get("label") not in STRICT_LABEL_SET or not (isinstance(v.get("confidence"), int)
                                                      and 1 <= v["confidence"] <= 5):
        raise ValueError(f"{path}: label must be one of {STRICT_LABEL_SET} and confidence an integer 1-5")
    return v


def needs_adjudication(a: dict, b: dict) -> bool:
    return a["label"] != b["label"] or min(a["confidence"], b["confidence"]) <= 3


def merge_strict_labels(src: Path, force: bool = False) -> None:
    """Fold <src>/{pass_a,pass_b,adjudication}/<item_id>.json into strict_labels.csv (H013-H098 only: the user's
    H001-H012 rows are never touched) and write the full audit, with the passes' agreement with the user's labels."""
    rows = _read_csv(STRICT_LABELS)
    by_id = {r["item_id"]: r for r in rows}
    # Items the user labelled outside H001-H012 (e.g. one whose adjudication couldn't be written) stay the user's.
    claude_items = [i for i in CLAUDE_ITEMS if by_id[i]["labeller"].strip().lower() != "user"]
    passes = {i: (_load_pass(src / "pass_a" / f"{i}.json"), _load_pass(src / "pass_b" / f"{i}.json")) for i in by_id}
    adjud = {i: _load_pass(src / "adjudication" / f"{i}.json") for i in by_id}
    missing = [i for i in by_id if None in passes[i]]
    to_adjudicate = [i for i in claude_items if None not in passes[i] and needs_adjudication(*passes[i])]
    pending = [i for i in to_adjudicate if adjud[i] is None]
    (src / "needs_adjudication.txt").write_text("\n".join(to_adjudicate) + "\n", encoding="utf-8")
    if missing or pending:
        print(f"not merged: {len(missing)} items lack a pass ({', '.join(missing)}); {len(pending)} need an "
              f"adjudication ({', '.join(pending)}). The full adjudication list is in {src / 'needs_adjudication.txt'}")
        return
    if any(by_id[i]["strict_label"].strip() for i in claude_items) and not force:
        print(f"{STRICT_LABELS} already has labels for {CLAUDE_ITEMS[0]}-{CLAUDE_ITEMS[-1]}; pass --force to replace")
        return

    audit = []
    for i in by_id:
        a, b = passes[i]
        entry = {"item_id": i, "category": by_id[i]["category"], "pass_a": a, "pass_b": b,
                 "adjudication": adjud[i] if i in to_adjudicate else None}
        if i in claude_items:
            final = adjud[i] if i in to_adjudicate else a
            by_id[i]["strict_label"] = final["label"]
            by_id[i]["labeller"] = ("claude-opus-5.5 adjudicator" if i in to_adjudicate
                                    else "claude-haiku-5.5 (two blind passes agree)")
            by_id[i]["notes"] = final.get("reason", "")
            entry["final"] = final["label"]
        else:
            entry["user_label"] = by_id[i]["strict_label"].strip().lower()
        audit.append(entry)
    calibration = labeller_calibration(audit)
    _write_strict_labels(rows)
    STRICT_AUDIT.write_text(json.dumps({"calibration_on_user_items": calibration, "items": audit}, indent=1,
                                       ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"merged {len(claude_items)} labels ({len(to_adjudicate)} adjudicated) into {STRICT_LABELS}; "
          f"audit in {STRICT_AUDIT}")
    print(f"Haiku passes vs the user on {USER_ITEMS[0]}-{USER_ITEMS[-1]}: {calibration}")


def labeller_calibration(audit: list[dict]) -> dict:
    """Agreement (%) and kappa of each Haiku pass, and of the labels both passes agree on, with the user's labels."""
    user = [e for e in audit if e.get("user_label") in STRICT_LABEL_SET and e["pass_a"] and e["pass_b"]]
    out: dict = {"n_user_labelled": len(user)}
    u = [e["user_label"] for e in user]
    for name in ("pass_a", "pass_b"):
        a = [e[name]["label"] for e in user]
        out[name] = {"agreement": agreement(a, u), "kappa": cohen_kappa(a, u)}
    agreed = [e for e in user if e["pass_a"]["label"] == e["pass_b"]["label"]]
    out["passes_agree"] = {"n": len(agreed), "agreement_with_user": agreement(
        [e["pass_a"]["label"] for e in agreed], [e["user_label"] for e in agreed])}
    return out
