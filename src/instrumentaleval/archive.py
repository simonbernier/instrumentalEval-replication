"""The raw results (responses, judge verdicts, strict-judge verdicts) as one compressed archive (ours, not upstream).

The three directories hold about 500 append-only files that nobody reads on GitHub, so git tracks
`results/raw.tar.xz` and a readable manifest (`results/raw_manifest.tsv`: path, bytes, SHA-256) instead, and ignores
the directories. `ie unpack-results` restores them, `ie pack-results` rebuilds the archive after new runs. The archive
is deterministic (sorted members, fixed metadata, LF line endings as git stores them), so packing unchanged data gives
the same bytes and git sees no change.
"""

import hashlib
import io
import lzma
import tarfile
from pathlib import Path

from . import RESULTS_DIR

RAW_DIRS = ("responses", "judgments", "strict_judgments")
ARCHIVE = RESULTS_DIR / "raw.tar.xz"
MANIFEST = RESULTS_DIR / "raw_manifest.tsv"
HEADER = "path\tbytes\tsha256"


def _canonical(path: Path) -> bytes:
    """The file as git stores it: a Windows checkout turns LF into CRLF, and JSON escapes every CR in content, so the
    only CRs in these text files are line endings."""
    return path.read_bytes().replace(b"\r\n", b"\n")


def raw_files(root: Path = RESULTS_DIR) -> list[Path]:
    """Every file under the raw directories, as paths relative to `root`, sorted."""
    return sorted(p.relative_to(root) for d in RAW_DIRS if (root / d).is_dir()
                  for p in (root / d).rglob("*") if p.is_file())


def read_manifest(manifest: Path = MANIFEST) -> dict[str, tuple[int, str]]:
    lines = manifest.read_text(encoding="utf-8").splitlines()
    assert lines[0] == HEADER, f"{manifest}: unexpected header {lines[0]!r}"
    return {path: (int(size), sha) for path, size, sha in (line.split("\t") for line in lines[1:])}


def pack(root: Path = RESULTS_DIR, archive: Path = ARCHIVE, manifest: Path = MANIFEST) -> tuple[int, int]:
    """Write the archive and its manifest from the raw directories under `root`. Returns (files, archive bytes)."""
    files = raw_files(root)
    rows, buf = [HEADER], io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for rel in files:
            data = _canonical(root / rel)
            name = rel.as_posix()
            info = tarfile.TarInfo(name)
            info.size, info.mtime, info.mode = len(data), 0, 0o644
            tar.addfile(info, io.BytesIO(data))
            rows.append(f"{name}\t{len(data)}\t{hashlib.sha256(data).hexdigest()}")
    archive.write_bytes(lzma.compress(buf.getvalue(), preset=9 | lzma.PRESET_EXTREME))
    manifest.write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")
    return len(files), archive.stat().st_size


def missing(root: Path = RESULTS_DIR, manifest: Path = MANIFEST) -> list[str]:
    """Manifest entries with no file on disk (a fresh clone before `ie unpack-results`)."""
    return [p for p in read_manifest(manifest) if not (root / p).is_file()]


def unpack(root: Path = RESULTS_DIR, archive: Path = ARCHIVE, manifest: Path = MANIFEST,
           force: bool = False) -> dict[str, list[str]]:
    """Restore the raw directories under `root`, checking every file against the manifest. A file already on disk
    that differs from the archive (e.g. records appended since the last pack) is left alone and reported as a
    conflict unless `force`. Returns {"written": [...], "unchanged": [...], "conflicts": [...]}."""
    expected = read_manifest(manifest)
    out: dict[str, list[str]] = {"written": [], "unchanged": [], "conflicts": []}
    with tarfile.open(fileobj=io.BytesIO(lzma.decompress(archive.read_bytes())), mode="r") as tar:
        members = {m.name: m for m in tar.getmembers() if m.isfile()}
        assert set(members) == set(expected), "archive and manifest list different files; re-run `ie pack-results`"
        for name in sorted(members):
            assert name.split("/")[0] in RAW_DIRS and ".." not in name.split("/"), f"unexpected member {name}"
            data = tar.extractfile(members[name]).read()
            assert (len(data), hashlib.sha256(data).hexdigest()) == expected[name], f"{name}: checksum mismatch"
            target = root / name
            if target.is_file():
                if _canonical(target) == data:
                    out["unchanged"].append(name)
                    continue
                if not force:
                    out["conflicts"].append(name)
                    continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            out["written"].append(name)
    return out
