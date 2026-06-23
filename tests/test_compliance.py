import pandas as pd
import pytest

from utils.compliance import PUBLISHED_SCHEDULE, compute_compliance_exceptions

EXPECTED = {"Retail": 0.0180, "E-commerce": 0.0240}


def _df(rows):
    return pd.DataFrame(rows)


def test_published_schedule_has_expected_categories_and_rates():
    assert PUBLISHED_SCHEDULE == {
        "Retail": 0.0180,
        "Travel": 0.0220,
        "Dining": 0.0195,
        "Healthcare": 0.0160,
        "E-commerce": 0.0240,
        "Fuel": 0.0145,
    }


def test_within_tolerance_not_flagged():
    df = _df([{
        "merchant_category": "Retail", "interchange_rate": 0.0181,
        "transaction_volume": 1_000_000, "avg_transaction_usd": 50.0,
    }])
    out = compute_compliance_exceptions(df, EXPECTED, tolerance_bps=15)
    assert bool(out.loc[0, "is_exception"]) is False
    assert out.loc[0, "direction"] == "Within tolerance"
    assert out.loc[0, "deviation_bps"] == pytest.approx(1.0)


def test_over_assessment_flagged_with_positive_impact():
    df = _df([{
        "merchant_category": "Retail", "interchange_rate": 0.0210,  # +30 bps
        "transaction_volume": 1_000_000, "avg_transaction_usd": 50.0,
    }])
    out = compute_compliance_exceptions(df, EXPECTED, tolerance_bps=15)
    assert bool(out.loc[0, "is_exception"]) is True
    assert out.loc[0, "deviation_bps"] == pytest.approx(30.0)
    assert out.loc[0, "direction"] == "Over-assessed"
    # (0.0210 - 0.0180) * 1_000_000 * 50 = 150_000
    assert out.loc[0, "financial_impact_usd"] == pytest.approx(150_000.0)


def test_under_assessment_flagged_with_negative_impact():
    df = _df([{
        "merchant_category": "E-commerce", "interchange_rate": 0.0210,  # -30 bps
        "transaction_volume": 2_000_000, "avg_transaction_usd": 40.0,
    }])
    out = compute_compliance_exceptions(df, EXPECTED, tolerance_bps=15)
    assert bool(out.loc[0, "is_exception"]) is True
    assert out.loc[0, "deviation_bps"] == pytest.approx(-30.0)
    assert out.loc[0, "direction"] == "Under-assessed"
    # (0.0210 - 0.0240) * 2_000_000 * 40 = -240_000
    assert out.loc[0, "financial_impact_usd"] == pytest.approx(-240_000.0)


def test_lower_tolerance_flags_more():
    df = _df([{
        "merchant_category": "Retail", "interchange_rate": 0.0190,  # +10 bps
        "transaction_volume": 1_000, "avg_transaction_usd": 10.0,
    }])
    strict = compute_compliance_exceptions(df, EXPECTED, tolerance_bps=5)
    loose = compute_compliance_exceptions(df, EXPECTED, tolerance_bps=15)
    assert bool(strict.loc[0, "is_exception"]) is True
    assert bool(loose.loc[0, "is_exception"]) is False


def test_mixed_rows_count_and_directions():
    df = _df([
        {"merchant_category": "Retail", "interchange_rate": 0.0181,
         "transaction_volume": 1_000, "avg_transaction_usd": 10.0},      # +1 bp within
        {"merchant_category": "Retail", "interchange_rate": 0.0210,
         "transaction_volume": 1_000, "avg_transaction_usd": 10.0},      # +30 over
        {"merchant_category": "E-commerce", "interchange_rate": 0.0200,
         "transaction_volume": 1_000, "avg_transaction_usd": 10.0},      # -40 under
    ])
    out = compute_compliance_exceptions(df, EXPECTED, tolerance_bps=15)
    assert int(out["is_exception"].sum()) == 2
    assert set(out["direction"]) == {"Within tolerance", "Over-assessed", "Under-assessed"}


def test_does_not_mutate_input():
    df = _df([{
        "merchant_category": "Retail", "interchange_rate": 0.0210,
        "transaction_volume": 1_000, "avg_transaction_usd": 10.0,
    }])
    compute_compliance_exceptions(df, EXPECTED, tolerance_bps=15)
    assert "is_exception" not in df.columns


def test_empty_input_returns_empty_with_columns():
    df = pd.DataFrame(columns=[
        "merchant_category", "interchange_rate",
        "transaction_volume", "avg_transaction_usd",
    ])
    out = compute_compliance_exceptions(df, EXPECTED, tolerance_bps=15)
    assert len(out) == 0
    for col in ["expected_rate", "deviation_bps", "is_exception",
                "financial_impact_usd", "direction"]:
        assert col in out.columns
