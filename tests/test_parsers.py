"""The pure parsing and arithmetic layer of the optimizer, exercised without Vivado.

These three functions decide what the optimizer believes about a design: whether timing improved,
whether the design is actually routed, and what f_max the numbers imply. Everything downstream —
autosave, legality gating, the break-even calculation — is built on them, so they are the part
worth pinning down in a test that anyone can run.
"""

from __future__ import annotations

import pytest

TIMING_REPORT = """
------------------------------------------------------------------------------------------------
| Design Timing Summary
| ---------------------
------------------------------------------------------------------------------------------------

    WNS(ns)      TNS(ns)  TNS Failing Endpoints  TNS Total Endpoints      WHS(ns)      THS(ns)
    -------      -------  ---------------------  -------------------      -------      -------
     -0.099       -1.449                     42               182934        0.014        0.000
"""

TIMING_REPORT_MET = """
    WNS(ns)      TNS(ns)  TNS Failing Endpoints  TNS Total Endpoints
    -------      -------  ---------------------  -------------------
      0.512        0.000                      0               182934
"""


def test_timing_summary_extracts_wns_tns_and_failing_endpoints(dcp_optimizer):
    result = dcp_optimizer.parse_timing_summary_static(TIMING_REPORT)
    assert result["wns"] == pytest.approx(-0.099)
    assert result["tns"] == pytest.approx(-1.449)
    assert result["failing_endpoints"] == 42


def test_timing_summary_handles_a_design_that_meets_timing(dcp_optimizer):
    result = dcp_optimizer.parse_timing_summary_static(TIMING_REPORT_MET)
    assert result["wns"] == pytest.approx(0.512)
    assert result["failing_endpoints"] == 0


@pytest.mark.parametrize("text", ["", "no table here", "WNS(ns) but no TNS header"])
def test_timing_summary_returns_empty_rather_than_guessing(dcp_optimizer, text):
    """A missing table must not become a fabricated WNS: downstream code treats None as
    'unknown' and refuses to bank a result, which is the safe direction."""
    assert dcp_optimizer.parse_timing_summary_static(text) == {
        "wns": None,
        "tns": None,
        "failing_endpoints": None,
    }


ROUTE_STATUS_CLEAN = """
Design Route Status
                                               :      # nets :
   ------------------------------------------- : ----------- :
   # of logical nets.......................... :      194302 :
   # of nets not needing routing.............. :       12006 :
   # of routable nets......................... :      182296 :
   # of fully routed nets..................... :      182296 :
   # of nets with routing errors.............. :           0 :
"""

ROUTE_STATUS_BROKEN = """
   # of routable nets......................... :      182296 :
   # of fully routed nets..................... :      182100 :
   # of unrouted nets......................... :         196 :
   # of nets with routing errors.............. :           4 :
"""

ROUTE_STATUS_UNPLACED = """
   # of routable nets......................... :           0 :
   # of fully routed nets..................... :           0 :
"""


def test_route_status_recognises_a_fully_routed_design(dcp_optimizer):
    result = dcp_optimizer.parse_route_status_static(ROUTE_STATUS_CLEAN)
    assert result["bad"] == 0
    assert result["routable"] == 182296
    assert result["fully_routed"] == 182296


def test_route_status_sums_every_negative_signal(dcp_optimizer):
    result = dcp_optimizer.parse_route_status_static(ROUTE_STATUS_BROKEN)
    assert result["bad"] == 200  # 196 unrouted + 4 routing errors
    assert result["fully_routed"] < result["routable"]


def test_route_status_flags_the_phantom_timing_case(dcp_optimizer):
    """Zero routable nets means the design is not really routed, and its WNS is estimated
    rather than real. Treating that as a win once produced an apparent +237 MHz that was not
    there; _design_is_legal rejects it on exactly this signal."""
    result = dcp_optimizer.parse_route_status_static(ROUTE_STATUS_UNPLACED)
    assert result["routable"] == 0


@pytest.mark.parametrize("value", [None, 42, b"bytes"])
def test_route_status_tolerates_non_text_input(dcp_optimizer, value):
    assert dcp_optimizer.parse_route_status_static(value)["bad"] == 0


FMAX_CASES = [
    # (wns, clock_period_ns, expected_mhz)
    (-0.099, 4.0, 1000.0 / 4.099),  # violating: the achievable period is longer
    (0.512, 4.0, 1000.0 / 3.488),  # met: slack shortens the achievable period
    (0.0, 2.5, 400.0),
]


@pytest.mark.parametrize(("wns", "period", "expected"), FMAX_CASES)
def test_fmax_arithmetic(dcp_optimizer, wns, period, expected):
    """Note that the implementation applies 1000/(period - wns) in both directions, including
    for positive slack; the docstring's 'fmax = 1/clock_period when WNS >= 0' describes a
    different rule than the code. The code's behaviour is what produced the published results,
    so it is what is pinned here."""
    base = dcp_optimizer.DCPOptimizerBase
    assert base.calculate_fmax(None, wns, period) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("wns", "period"),
    [(None, 4.0), (-0.5, None), (-0.5, 0.0), (-0.5, -1.0), (5.0, 4.0)],
)
def test_fmax_refuses_to_invent_a_number(dcp_optimizer, wns, period):
    """Missing inputs, a non-positive clock and slack exceeding the period all return None
    rather than a nonsensical frequency."""
    base = dcp_optimizer.DCPOptimizerBase
    assert base.calculate_fmax(None, wns, period) is None
