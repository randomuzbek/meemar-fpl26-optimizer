"""The packager's exclusion rules, which is where packaging failures actually came from.

Every rule asserted here corresponds to something that broke a real evaluation run. See
docs/reproduce.md for the incidents.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def pack():
    spec = importlib.util.spec_from_file_location("pack_tool", REPO_ROOT / "tools" / "pack.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["pack_tool"] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "rel",
    [
        "fpl26_optimization_contest/__pycache__/dcp_optimizer.cpython-311.pyc",
        "fpl26_optimization_contest/RapidWright/build/libs/rapidwright.jar",
        "fpl26_optimization_contest/node_modules/x/index.js",
        "fpl26_optimization_contest/.pytest_cache/v/cache/lastfailed",
    ],
)
def test_build_and_cache_directories_are_excluded(pack, rel):
    assert pack._should_skip(Path(rel)) is True


@pytest.mark.parametrize(
    "rel",
    [
        # ~500 MB of benchmarks the evaluator already has, as a directory...
        "fpl26_optimization_contest/fpl26_contest_benchmarks/boom.dcp",
        # ...and as the tarball, which slips past both the exact-name and the suffix rule.
        "fpl26_optimization_contest/fpl26_contest_benchmarks_v1.1.0.tar.gz",
        # Past run directories carry a timestamp suffix, so they need a prefix match.
        "fpl26_optimization_contest/dcp_optimizer_run-20260805_2258/vivado.log",
    ],
)
def test_bulk_and_run_output_is_excluded_by_prefix(pack, rel):
    assert pack._should_skip(Path(rel)) is True


@pytest.mark.parametrize(
    "rel",
    [
        "fpl26_optimization_contest/x.pyc",
        "fpl26_optimization_contest/vivado.log",
        "fpl26_optimization_contest/vivado.jou",
        "fpl26_optimization_contest/design.dcp",
        "fpl26_optimization_contest/top.bit",
    ],
)
def test_toolchain_output_suffixes_are_excluded(pack, rel):
    assert pack._should_skip(Path(rel)) is True


@pytest.mark.parametrize(
    "rel",
    [
        "fpl26_optimization_contest/dcp_optimizer.py",
        "fpl26_optimization_contest/Makefile",
        "fpl26_optimization_contest/SYSTEM_PROMPT.TXT",
        "fpl26_optimization_contest/requirements.txt",
        "fpl26_optimization_contest/validate_dcps.py",
        "fpl26_optimization_contest/RapidWright/gradlew",
        "fpl26_optimization_contest/VivadoMCP/vivado_mcp_server.py",
    ],
)
def test_everything_the_evaluator_needs_survives(pack, rel):
    assert pack._should_skip(Path(rel)) is False


@pytest.mark.parametrize(
    ("arcname", "expected"),
    [
        ("fpl26_optimization_contest/RapidWright/gradlew", 0o100755),
        ("fpl26_optimization_contest/setup.sh", 0o100755),
        ("fpl26_optimization_contest/dcp_optimizer.py", 0o100644),
        ("fpl26_optimization_contest/README.md", 0o100644),
    ],
)
def test_executable_bits_survive_a_windows_build(pack, arcname, expected):
    """Windows carries no Unix exec bit, so a naive zip stores everything non-executable and
    `make setup` dies at './gradlew: Permission denied'. The name-based fallback covers gradlew
    and *.sh even when the git index is unavailable."""
    assert pack._zip_unix_mode(arcname, set()) == expected


def test_git_index_can_mark_anything_executable(pack):
    arc = "fpl26_optimization_contest/tools/weird_name"
    assert pack._zip_unix_mode(arc, set()) == 0o100644
    assert pack._zip_unix_mode(arc, {arc}) == 0o100755


def test_preflight_reports_a_missing_contest_directory(pack, tmp_path):
    pack.CONTEST_DIR = tmp_path / "does-not-exist"
    report = pack.preflight()
    assert report.ok is False
    assert report.missing


def test_preflight_lists_every_required_file_that_is_absent(pack, tmp_path):
    contest = tmp_path / "fpl26_optimization_contest"
    contest.mkdir()
    (contest / "dcp_optimizer.py").write_text("# stub\n", encoding="utf-8")
    pack.CONTEST_DIR = contest

    report = pack.preflight()
    assert report.ok is False
    assert "dcp_optimizer.py" not in report.missing
    assert "Makefile" in report.missing
    assert "SYSTEM_PROMPT.TXT" in report.missing
