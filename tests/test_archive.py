"""The raw-results archive: deterministic packing, a checked round trip, conflicts and the missing-file guard. Offline,
on a small tree in tmp_path."""

from instrumentaleval.archive import missing, pack, read_manifest, unpack


def _tree(root):
    (root / "responses").mkdir(parents=True)
    (root / "judgments" / "gpt-4o").mkdir(parents=True)
    (root / "responses" / "m__nudge__benchmark.jsonl").write_bytes(b'{"task_id": "ES-01"}\n{"task_id": "ES-02"}\n')
    # a Windows checkout: git turned LF into CRLF
    (root / "judgments" / "gpt-4o" / "m__nudge__benchmark.jsonl").write_bytes(b'{"conv": true}\r\n')
    (root / "tables.md").write_text("not raw", encoding="utf-8")


def test_pack_is_deterministic_and_lists_raw_files_only(tmp_path):
    src = tmp_path / "src"
    _tree(src)
    a1, m1 = tmp_path / "a1.tar.xz", tmp_path / "m1.tsv"
    a2, m2 = tmp_path / "a2.tar.xz", tmp_path / "m2.tsv"
    assert pack(src, a1, m1)[0] == 2
    pack(src, a2, m2)
    assert a1.read_bytes() == a2.read_bytes() and m1.read_bytes() == m2.read_bytes()
    entries = read_manifest(m1)
    assert list(entries) == ["judgments/gpt-4o/m__nudge__benchmark.jsonl", "responses/m__nudge__benchmark.jsonl"]
    assert entries["judgments/gpt-4o/m__nudge__benchmark.jsonl"][0] == len(b'{"conv": true}\n')  # stored as LF


def test_round_trip_conflicts_and_missing(tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    _tree(src)
    archive, manifest = tmp_path / "raw.tar.xz", tmp_path / "raw.tsv"
    pack(src, archive, manifest)
    assert len(missing(dst, manifest)) == 2

    out = unpack(dst, archive, manifest)
    assert len(out["written"]) == 2 and not out["conflicts"] and not missing(dst, manifest)
    assert (dst / "responses" / "m__nudge__benchmark.jsonl").read_bytes() == \
        (src / "responses" / "m__nudge__benchmark.jsonl").read_bytes()
    assert len(unpack(dst, archive, manifest)["unchanged"]) == 2

    # a record appended since the last pack is never overwritten silently
    target = dst / "responses" / "m__nudge__benchmark.jsonl"
    target.write_bytes(target.read_bytes() + b'{"task_id": "ES-03"}\n')
    assert unpack(dst, archive, manifest)["conflicts"] == ["responses/m__nudge__benchmark.jsonl"]
    assert b"ES-03" in target.read_bytes()
    assert unpack(dst, archive, manifest, force=True)["written"] == ["responses/m__nudge__benchmark.jsonl"]
    assert b"ES-03" not in target.read_bytes()
