import math

from build_fundamental_valuation_suite import dcf_equity_value, implied_growth


def test_dcf_is_ordered_by_growth_and_discount() -> None:
    low = dcf_equity_value(100, 20, 10, 0.03, 0.14, 0.03)
    base = dcf_equity_value(100, 20, 10, 0.08, 0.12, 0.04)
    high = dcf_equity_value(100, 20, 10, 0.12, 0.11, 0.05)
    assert 0 < low < base < high


def test_reverse_dcf_recovers_growth() -> None:
    target = dcf_equity_value(177.11, -96.3, 10, 0.08, 0.12, 0.04)
    result = implied_growth(target, 177.11, -96.3, 10, 0.12, 0.04)
    assert math.isclose(result, 0.08, abs_tol=1e-6)
