"""Import the frozen submission without a toolchain.

`submission/dcp_optimizer.py` imports `mcp` at module scope, and `mcp` exists only inside the
contest harness. The whole point of this test suite is that it runs on a machine with no Vivado,
no RapidWright and no MCP servers, so the import is satisfied with a stub before the module is
loaded. Nothing under test touches the stub: the functions exercised here are pure.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SUBMISSION = REPO_ROOT / "submission" / "dcp_optimizer.py"


def _install_mcp_stub() -> None:
    if "mcp" in sys.modules:
        return

    mcp = types.ModuleType("mcp")
    mcp.ClientSession = object
    mcp.StdioServerParameters = object

    client = types.ModuleType("mcp.client")
    stdio = types.ModuleType("mcp.client.stdio")

    def stdio_client(*_args, **_kwargs):  # pragma: no cover - never called in these tests
        raise RuntimeError("stdio_client is stubbed; these tests must not start MCP servers")

    stdio.stdio_client = stdio_client
    client.stdio = stdio

    sys.modules["mcp"] = mcp
    sys.modules["mcp.client"] = client
    sys.modules["mcp.client.stdio"] = stdio


@pytest.fixture(scope="session")
def dcp_optimizer():
    """The frozen submission module, imported under a stubbed MCP."""
    _install_mcp_stub()
    spec = importlib.util.spec_from_file_location("dcp_optimizer_frozen", SUBMISSION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["dcp_optimizer_frozen"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT
