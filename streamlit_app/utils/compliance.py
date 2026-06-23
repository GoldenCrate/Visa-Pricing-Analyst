import numpy as np
import pandas as pd

# Published interchange schedule — the standard rate each merchant category
# should be assessed (the "rate card" compliance is measured against).
PUBLISHED_SCHEDULE = {
    "Retail": 0.0180,
    "Travel": 0.0220,
    "Dining": 0.0195,
    "Healthcare": 0.0160,
    "E-commerce": 0.0240,
    "Fuel": 0.0145,
}


def compute_compliance_exceptions(
    df: pd.DataFrame,
    expected_rates: dict,
    tolerance_bps: float,
) -> pd.DataFrame:
    """
    Audit assessed interchange against the published schedule.

    Adds, per row:
      expected_rate         - published rate for the row's merchant_category
      deviation_bps         - (interchange_rate - expected_rate) * 10000 (signed)
      is_exception          - abs(deviation_bps) > tolerance_bps
      financial_impact_usd  - (interchange_rate - expected_rate)
                              * transaction_volume * avg_transaction_usd (signed;
                              positive = over-assessed, negative = under-assessed)
      direction             - "Over-assessed" / "Under-assessed" / "Within tolerance"

    Returns a new DataFrame; the input is not mutated.
    """
    result = df.copy()
    result["expected_rate"] = result["merchant_category"].map(expected_rates)
    rate_delta = result["interchange_rate"] - result["expected_rate"]
    result["deviation_bps"] = rate_delta * 10000
    result["is_exception"] = result["deviation_bps"].abs() > tolerance_bps
    result["financial_impact_usd"] = (
        rate_delta * result["transaction_volume"] * result["avg_transaction_usd"]
    )
    result["direction"] = np.where(
        ~result["is_exception"],
        "Within tolerance",
        np.where(result["deviation_bps"] > 0, "Over-assessed", "Under-assessed"),
    )
    return result
