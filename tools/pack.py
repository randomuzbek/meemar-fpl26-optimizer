"""Submission packager — build a deterministic zip of the contest repo.

What goes into the zip:
  - The entire `fpl26_optimization_contest/` submodule contents
  - A `meemar_manifest.json` at the top level recording build provenance:
      git_sha, build_ts, host, files (path → MD5), zip_md5

Why a manifest:
  - We can later prove which exact commit was submitted
  - Diff against an earlier submission to see what changed
  - Cross-check that all expected files are present before upload

The zip is stored under `artifacts/submissions/<round>__<git_sha8>__<ts>.zip`
and a sibling `.json` carries the manifest.

This is the exact packager that produced the scored final submission
(zip md5 `3c0bd8d702078d4c2158a0e6c8789868`). Its comments record four
packaging failures that each cost a preview run; read them before changing
anything about how bytes, modes or timestamps reach the archive.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import tarfile
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Resolved at import time from the environment so the packager can be pointed at any
# checkout of the contest repository:
#   FPL26_CONTEST_DIR   path to the fpl26_optimization_contest checkout to package
#   FPL26_ARTIFACT_DIR  where the zip and its manifest are written
REPO_ROOT = Path(__file__).resolve().parent.parent
CONTEST_DIR = Path(
    os.environ.get("FPL26_CONTEST_DIR", REPO_ROOT / "fpl26_optimization_contest")
).resolve()
ARTIFACT_ROOT = Path(
    os.environ.get("FPL26_ARTIFACT_DIR", REPO_ROOT / "artifacts" / "submissions")
).resolve()

# Files we expect to find in any valid submission. Pre-flight checks them.
REQUIRED_PATHS = [
    "Makefile",
    "dcp_optimizer.py",
    "validate_dcps.py",
    "requirements.txt",
    "SYSTEM_PROMPT.TXT",
    "RapidWrightMCP",
    "VivadoMCP",
    "RapidWright",
]

# Exclusions — never ship these inside the zip
EXCLUDE_DIRS = {
    "__pycache__",
    ".pytest_cache",
    "fpl26_contest_benchmarks",  # ~500MB, downloaded at make setup
    "dcp_optimizer_run-",  # past run dirs (timestamp suffix)
    ".Xil",
    "build",  # gradle build dir
    "node_modules",
}
EXCLUDE_SUFFIXES = {".pyc", ".log", ".jou", ".dcp", ".bit", ".ltx"}


@dataclass
class PackagedSubmission:
    zip_path: Path
    manifest_path: Path
    manifest: dict[str, Any]
    size_bytes: int
    files_included: int
    md5_zip: str


@dataclass
class PreflightReport:
    ok: bool
    missing: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _git_sha(cwd: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(cwd),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def _md5(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _should_skip(rel: Path) -> bool:
    parts = set(rel.parts)
    if parts & EXCLUDE_DIRS:
        return True
    # match prefix-style excludes (e.g. dcp_optimizer_run-2026...) and the benchmark
    # archive/dir (fpl26_contest_benchmarks{,_v1.1.0.tar.gz}) -- the latter is a ~500MB
    # benchmark blob the evaluator already has; a stray .tar.gz of it slips past the exact
    # EXCLUDE_DIRS name match and (being .gz) past EXCLUDE_SUFFIXES, so guard the prefix.
    for p in rel.parts:
        if p.startswith("dcp_optimizer_run-") or p.startswith("fpl26_contest_benchmarks"):
            return True
    if rel.suffix in EXCLUDE_SUFFIXES:
        return True
    return False


def preflight() -> PreflightReport:
    """Verify the contest dir has the files an evaluator needs."""
    rep = PreflightReport(ok=True)
    if not CONTEST_DIR.exists():
        rep.ok = False
        rep.missing.append(str(CONTEST_DIR))
        return rep

    for rel in REQUIRED_PATHS:
        target = CONTEST_DIR / rel
        if not target.exists():
            rep.ok = False
            rep.missing.append(rel)

    # Submodule pointer sanity: RapidWright submodule should not be empty
    rw = CONTEST_DIR / "RapidWright"
    if rw.is_dir() and not any(rw.iterdir()):
        rep.warnings.append(
            "RapidWright submodule appears empty (run `git submodule update --init`)"
        )

    return rep


def _git_tracked_relposix(root: Path) -> set[str] | None:
    """Set of repo-tracked files under `root` as POSIX paths relative to `root`, recursing
    into nested submodules (RapidWright/VivadoMCP/RapidWrightMCP). Returns None if git is
    unavailable so the caller falls back to a full filesystem walk (packaging never breaks).

    Why: the packager walks the working tree, which also contains untracked dev-scratch
    (agent*.py crosstabs, _tmp_*.py, *_results.json). Those are info-leak, not DQ, but the
    submission should be exactly the committed tree -- the equivalent of `git archive`. Every
    REQUIRED_PATH is tracked, so restricting to the tracked set drops only scratch."""
    try:
        out = subprocess.check_output(
            ["git", "ls-files", "--recurse-submodules"],
            cwd=str(root),
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return None
    tracked = {line.strip() for line in out.splitlines() if line.strip()}
    return tracked or None


def _git_exec_arcnames(root: Path) -> set[str]:
    """Arcnames (root.name/<relpath>) of files marked executable (100755) in the git index,
    recursing into submodules (RapidWright etc.).

    Why: the zip is built on Windows, where the working tree carries no Unix exec bits, so
    zipfile stores every entry non-executable. The contest validator's `make setup` then dies
    at `./gradlew: Permission denied` (beta preview attempt #2, md5 15325f98, 2026-07-02).
    The git index is the source of truth for the intended modes (RapidWright/gradlew is
    committed 100755). Returns empty set if git is unavailable -- the name-based fallback in
    _zip_unix_mode still covers gradlew/*.sh."""
    try:
        out = subprocess.check_output(
            ["git", "ls-files", "-s", "--recurse-submodules"],
            cwd=str(root),
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return set()
    execs: set[str] = set()
    for line in out.splitlines():
        meta, _, path = line.partition("\t")
        if path and meta.split()[0] == "100755":
            execs.add(f"{root.name}/{path.strip()}")
    return execs


def _git_archive_contents(repo_root: Path) -> dict[str, tuple[bytes, int]]:
    """relpath -> (committed bytes, unix mode) via `git archive HEAD` of repo_root.

    Why blobs, not the worktree: on Windows the checkout is CRLF-smudged. Shipping worktree
    bytes sent a gradlew whose shebang read `#!/usr/bin/env sh\\r` -- the validator's kernel
    can't exec that (`/usr/bin/env: 'sh\\r': No such file or directory`, beta preview attempt
    #4, 2026-07-02). The committed blob is the LF truth, and git archive also carries the
    intended exec bits. Returns empty dict if git is unavailable (caller falls back to
    worktree bytes + name-based modes)."""
    try:
        # -c overrides matter: git archive applies the SAME autocrlf/eol smudge as checkout
        # (verified: without them the tar still carried CRLF gradlew despite reading "blobs").
        raw = subprocess.check_output(
            [
                "git",
                "-c",
                "core.autocrlf=false",
                "-c",
                "core.eol=lf",
                "archive",
                "--format=tar",
                "HEAD",
            ],
            cwd=str(repo_root),
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return {}
    out: dict[str, tuple[bytes, int]] = {}
    with tarfile.open(fileobj=io.BytesIO(raw)) as tf:
        for member in tf.getmembers():
            if member.isfile():
                fh = tf.extractfile(member)
                if fh is not None:
                    out[member.name] = (fh.read(), member.mode)
    return out


def _zip_unix_mode(arcname: str, exec_arcnames: set[str]) -> int:
    basename = arcname.rsplit("/", 1)[-1]
    if arcname in exec_arcnames or basename == "gradlew" or basename.endswith(".sh"):
        return 0o100755
    return 0o100644


def _iter_files(root: Path, tracked: set[str] | None = None):
    """Yield (abs_path, rel_path) under root, applying skip rules. When `tracked` (a set of
    git-tracked POSIX paths relative to root) is provided, untracked files are skipped so
    dev-scratch never reaches the zip; None => ship the full walk (git-less fallback)."""
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if tracked is not None and path.relative_to(root).as_posix() not in tracked:
            continue  # untracked dev-scratch -> keep it out
        rel = path.relative_to(root.parent)  # ship under fpl26_optimization_contest/...
        if _should_skip(rel):
            continue
        yield path, rel


def package(
    round_name: str,
    output_dir: Path | None = None,
    *,
    extra_metadata: dict[str, Any] | None = None,
    include_manifest: bool = False,
) -> PackagedSubmission:
    """Build the submission zip. Returns paths and stats.

    include_manifest ships `meemar_manifest.json` INSIDE the archive. Default False.

    Why default off: the final-round preview harness rejected every archive that carried it
    with `trusted_validator_missing`, and every archive that passed lacked it (2026-08-04).
    The manifest is confounded with our setup-file changes in that experiment, so we cannot
    yet say which one the harness objects to -- but the manifest is pure team-side provenance
    with no functional role in evaluation, so the cheap and safe move is to stop shipping it.
    The sidecar `.json` next to the zip still records full provenance either way.
    """
    pre = preflight()
    if not pre.ok:
        raise RuntimeError(f"Preflight failed. Missing: {pre.missing}. Warnings: {pre.warnings}")

    git_sha = _git_sha(REPO_ROOT)
    git_sha8 = git_sha[:8] if git_sha != "unknown" else "nogit"
    ts = time.strftime("%Y%m%d_%H%M%S")

    out_dir = Path(output_dir) if output_dir else ARTIFACT_ROOT
    out_dir.mkdir(parents=True, exist_ok=True)

    zip_path = out_dir / f"{round_name}__{git_sha8}__{ts}.zip"
    manifest_path = zip_path.with_suffix(".json")

    files_md5: dict[str, str] = {}
    files_included = 0

    # Git-aware allowlist: ship only the tracked tree (drops untracked dev-scratch). Falls
    # back to a full walk if git is unavailable, with a preflight-style warning recorded below.
    tracked = _git_tracked_relposix(CONTEST_DIR)
    if tracked is None:
        pre.warnings.append(
            "git unavailable; shipping full working tree (untracked files included)"
        )

    exec_arcnames = _git_exec_arcnames(CONTEST_DIR)
    if not exec_arcnames:
        pre.warnings.append("git exec-bit index unavailable; relying on gradlew/*.sh name fallback")

    # Committed (LF, exec-bit-true) content beats the CRLF-smudged Windows worktree.
    committed = _git_archive_contents(CONTEST_DIR)
    for rel, item in _git_archive_contents(CONTEST_DIR / "RapidWright").items():
        committed[f"RapidWright/{rel}"] = item
    if not committed:
        pre.warnings.append(
            "git archive unavailable; shipping worktree bytes (CRLF/exec-bit hazard on Windows)"
        )
    try:
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=str(CONTEST_DIR),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if dirty and committed:
            pre.warnings.append(
                "tracked files have UNCOMMITTED changes; the zip ships COMMITTED content, "
                "so those edits are NOT included:\n" + dirty
            )
    except Exception:
        pass

    # Fixed entry timestamp (HEAD commit time): zip stores naive local time, and shipping
    # "now" from a TZ ahead of the validator triggers make's clock-skew warnings
    # ("File 'Makefile' has modification time N s in the future").
    try:
        head_ct = int(
            subprocess.check_output(
                ["git", "log", "-1", "--format=%ct"],
                cwd=str(CONTEST_DIR),
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        )
    except Exception:
        head_ct = int(time.time()) - 86400
    entry_dt = time.gmtime(head_ct)[:6]

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for abs_path, rel_path in _iter_files(CONTEST_DIR, tracked):
            arcname = rel_path.as_posix()
            rel_repo = rel_path.relative_to(rel_path.parts[0]).as_posix()
            entry = committed.get(rel_repo)
            if entry is not None:
                data, tar_mode = entry
                mode = 0o100755 if tar_mode & 0o111 else 0o100644
            else:  # untarred-but-shipped (shouldn't happen for tracked files) -> worktree fallback
                data = abs_path.read_bytes()
                mode = _zip_unix_mode(arcname, exec_arcnames)
            zi = zipfile.ZipInfo(arcname, date_time=entry_dt)
            zi.create_system = 3
            zi.external_attr = mode << 16
            zi.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(zi, data)
            files_md5[arcname] = hashlib.md5(data).hexdigest()
            files_included += 1

        # Manifest goes inside the zip as well as next to it
        manifest = {
            "round": round_name,
            "git_sha": git_sha,
            "git_sha_short": git_sha8,
            "build_ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "host": os.environ.get("HOSTNAME") or os.environ.get("COMPUTERNAME") or "unknown",
            "files_count": files_included,
            "files_md5": files_md5,
            "preflight_warnings": pre.warnings,
            "extra": extra_metadata or {},
        }
        # Write the manifest INSIDE the single top-level dir (opt-in) so the archive has
        # exactly ONE top-level entry (fpl26_optimization_contest/). The contest
        # validator unpacks the archive and cd's into the submission's sole
        # top-level directory before running `make setup`; a second root-level
        # entry (a bare manifest.json) breaks that detection, so `make setup`
        # runs in the wrong directory -> "No rule to make target 'setup'" ->
        # setup_failed on every benchmark (observed in beta preview attempt #1,
        # md5 c8ad3461). Alpha passed because it predated this packager and
        # shipped a single top-level dir.
        if include_manifest:
            zi = zipfile.ZipInfo(
                "fpl26_optimization_contest/meemar_manifest.json", date_time=entry_dt
            )
            zi.create_system = 3
            zi.external_attr = 0o100644 << 16
            zi.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(zi, json.dumps(manifest, indent=2))
            files_included += 1

    md5_zip = _md5(zip_path)
    manifest["zip_md5"] = md5_zip
    manifest["zip_size_bytes"] = zip_path.stat().st_size
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return PackagedSubmission(
        zip_path=zip_path,
        manifest_path=manifest_path,
        manifest=manifest,
        size_bytes=manifest["zip_size_bytes"],
        files_included=files_included,
        md5_zip=md5_zip,
    )


def main(argv: list[str] | None = None) -> int:
    global CONTEST_DIR
    import argparse

    ap = argparse.ArgumentParser(
        description="Build a deterministic submission zip from a contest checkout.",
    )
    ap.add_argument(
        "--contest-dir",
        type=Path,
        default=CONTEST_DIR,
        help="path to the fpl26_optimization_contest checkout (default: $FPL26_CONTEST_DIR)",
    )
    ap.add_argument("--round", default="final", help="round name used in the zip filename")
    ap.add_argument("--out", type=Path, default=None, help="output directory for the zip")
    ap.add_argument(
        "--include-manifest",
        action="store_true",
        help="ship meemar_manifest.json inside the archive (see package() docstring: don't)",
    )
    args = ap.parse_args(argv)

    CONTEST_DIR = args.contest_dir.resolve()

    result = package(args.round, args.out, include_manifest=args.include_manifest)
    print(f"zip      {result.zip_path}")
    print(f"manifest {result.manifest_path}")
    print(f"files    {result.files_included}")
    print(f"bytes    {result.size_bytes}")
    print(f"md5      {result.md5_zip}")
    for w in result.manifest.get("preflight_warnings", []):
        print(f"warning  {w}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
