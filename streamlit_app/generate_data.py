"""
Run this script once to generate the synthetic dataset.
  python generate_data.py
"""

import csv
import random
from datetime import date, timedelta

random.seed(42)

# Dedicated RNG for compliance-anomaly injection. Kept separate from the main
# `random` stream so non-anomalous rows are identical to the prior dataset.
anomaly_rng = random.Random(1234)
anomaly_count = 0

REGIONS = {
    "North America":   {"vol_base": 12_000_000, "accept_base": 0.96},
    "Europe":          {"vol_base":  9_000_000, "accept_base": 0.94},
    "Asia Pacific":    {"vol_base":  8_500_000, "accept_base": 0.91},
    "Latin America":   {"vol_base":  4_000_000, "accept_base": 0.87},
    "Middle East & Africa": {"vol_base": 2_500_000, "accept_base": 0.83},
}

MERCHANT_CATEGORIES = {
    "Retail":      {"interchange_base": 0.0180},
    "Travel":      {"interchange_base": 0.0220},
    "Dining":      {"interchange_base": 0.0195},
    "Healthcare":  {"interchange_base": 0.0160},
    "E-commerce":  {"interchange_base": 0.0240},
    "Fuel":        {"interchange_base": 0.0145},
}

CARD_TYPES = {
    "Credit":  {"share": 0.52, "avg_txn_usd": 85},
    "Debit":   {"share": 0.38, "avg_txn_usd": 42},
    "Prepaid": {"share": 0.10, "avg_txn_usd": 28},
}

def month_range(start: date, end: date):
    d = start.replace(day=1)
    while d <= end:
        yield d
        # advance one month
        if d.month == 12:
            d = d.replace(year=d.year + 1, month=1)
        else:
            d = d.replace(month=d.month + 1)

rows = []
start_date = date(2024, 1, 1)
end_date   = date(2025, 12, 1)

for month in month_range(start_date, end_date):
    # gentle upward trend factor
    months_elapsed = (month.year - start_date.year) * 12 + (month.month - start_date.month)
    trend = 1 + months_elapsed * 0.004

    for region, rparams in REGIONS.items():
        for category, cparams in MERCHANT_CATEGORIES.items():
            for card_type, kparams in CARD_TYPES.items():
                # transaction volume
                vol = int(
                    rparams["vol_base"]
                    * kparams["share"]
                    * trend
                    * random.uniform(0.92, 1.08)
                )

                # interchange rate (slight seasonal bump in Q4)
                seasonal = 1.015 if month.month in (10, 11, 12) else 1.0
                interchange_rate = round(
                    cparams["interchange_base"] * seasonal * random.uniform(0.97, 1.03), 4
                )

                # Compliance anomaly injection: ~2.5% of rows are materially
                # mis-assessed (20-60 bps off the published schedule, either
                # direction) to simulate interchange processing errors for the
                # Compliance Monitor page. Uses a separate RNG so other rows are
                # unchanged. revenue (computed below) reflects the assessed rate.
                if anomaly_rng.random() < 0.025:
                    delta = anomaly_rng.uniform(0.0020, 0.0060) * anomaly_rng.choice([-1, 1])
                    interchange_rate = round(
                        max(0.0010, cparams["interchange_base"] + delta), 4
                    )
                    anomaly_count += 1

                # revenue = vol * avg_txn_value * interchange_rate
                avg_txn = kparams["avg_txn_usd"] * random.uniform(0.95, 1.05)
                revenue = round(vol * avg_txn * interchange_rate, 2)

                # acceptance rate
                acceptance_rate = round(
                    min(0.999, rparams["accept_base"] * random.uniform(0.99, 1.01)), 4
                )

                rows.append({
                    "month":             month.isoformat(),
                    "region":            region,
                    "merchant_category": category,
                    "card_type":         card_type,
                    "transaction_volume": vol,
                    "avg_transaction_usd": round(avg_txn, 2),
                    "interchange_rate":  interchange_rate,
                    "revenue_usd":       revenue,
                    "acceptance_rate":   acceptance_rate,
                })

out_path = "data/visa_pricing_metrics.csv"
with open(out_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print(f"Written {len(rows):,} rows to {out_path}")
print(f"Injected {anomaly_count} interchange anomalies")
