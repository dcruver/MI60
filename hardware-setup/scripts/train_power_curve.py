#!/usr/bin/env python3
"""
Build a Power → PWM Curve from Historical Fan Control Data.

This script analyzes the CSV log from gpu-fan-control to determine what PWM values
actually kept temperatures safe at each GPU power draw level. Power is more directly
causal to heat generation than utilization.

METHODOLOGY:
1. Load all samples from /var/log/gpu-fan-control.csv (new format with power)
2. Filter to "safe" samples where max_temp <= TARGET_TEMP
3. For each 25W power bucket, find the median PWM of safe samples
4. Enforce monotonicity: higher power never gets lower PWM
5. Output the curve in a format ready for ml-fan-control.py

WHY POWER > UTILIZATION:
- Power (watts) directly causes heat generation (P = heat)
- Utilization can be 100% with varying power depending on workload type
- Power captures memory-bound vs compute-bound differences

USAGE:
    python train_power_curve.py

After running, copy the POWER_PWM_POINTS output into ml-fan-control.py and restart
the service.
"""

import pandas as pd
import numpy as np
from pathlib import Path

CSV_PATH = "/var/log/gpu-fan-control.csv"
TARGET_TEMP = 85.0
POWER_BUCKET_SIZE = 25  # 25W buckets


def load_data(csv_path: str) -> pd.DataFrame:
    """Load CSV with new format including power columns."""
    df = pd.read_csv(
        csv_path,
        names=["timestamp", "gpu0_temp", "gpu0_util", "gpu0_power",
               "gpu1_temp", "gpu1_util", "gpu1_power",
               "max_temp", "max_util", "max_power", "pwm"],
        parse_dates=["timestamp"],
    )
    return df


def analyze_and_build_power_curve(df: pd.DataFrame, target_temp: float):
    """
    Build a monotonic PWM curve from power draw.

    For each power bucket:
    1. Find all samples where temp stayed safe
    2. Determine the minimum PWM that achieved this reliably (75th percentile)
    3. Enforce monotonicity (higher power never gets lower PWM)
    """

    print(f"Building POWER-based curve for target temp: {target_temp}°C")
    print(f"Total samples: {len(df):,}")

    # Filter to safe samples
    safe_df = df[df["max_temp"] <= target_temp].copy()
    print(f"Safe samples (temp <= {target_temp}°C): {len(safe_df):,}")

    # Also show utilization curve for comparison
    print("\n" + "=" * 70)
    print("COMPARISON: Utilization vs Power based curves")
    print("=" * 70)

    # Analyze by power bucket (25W increments)
    results = []
    max_power = int(df["max_power"].max())
    power_range = range(0, max_power + POWER_BUCKET_SIZE, POWER_BUCKET_SIZE)

    print(f"\n{'Power':<10} {'Safe':<10} {'Total':<10} {'Avg Temp':<10} {'PWM p50':<10} {'PWM p75':<10}")
    print("-" * 70)

    for power in power_range:
        power_low = power
        power_high = power + POWER_BUCKET_SIZE

        # All samples in this power range
        all_mask = (df["max_power"] >= power_low) & (df["max_power"] < power_high)
        all_samples = df[all_mask]

        # Safe samples in this power range
        safe_mask = (safe_df["max_power"] >= power_low) & (safe_df["max_power"] < power_high)
        safe_samples = safe_df[safe_mask]

        if len(safe_samples) < 10:
            pwm_p50 = pwm_p75 = 255
            avg_temp = 0
        else:
            pwm_p50 = safe_samples["pwm"].quantile(0.50)
            pwm_p75 = safe_samples["pwm"].quantile(0.75)
            avg_temp = safe_samples["max_temp"].mean()

        results.append({
            "power": power,
            "safe_count": len(safe_samples),
            "total_count": len(all_samples),
            "avg_temp": avg_temp,
            "pwm_p50": pwm_p50,
            "pwm_p75": pwm_p75,
        })

        if len(all_samples) > 0:  # Only print non-empty buckets
            print(f"{power:>3}-{power_high:<3}W  {len(safe_samples):<10} {len(all_samples):<10} "
                  f"{avg_temp:<10.1f} {pwm_p50:<10.0f} {pwm_p75:<10.0f}")

    # Build monotonic curve using p75 (more conservative for safety)
    print("\n=== Building Monotonic Power Curve ===")

    # Start with raw values
    raw_curve = {r["power"]: r["pwm_p75"] for r in results if r["total_count"] > 0}

    # Enforce monotonicity: each higher power level must have >= PWM
    monotonic_curve = {}
    max_pwm_so_far = 110

    for power in sorted(raw_curve.keys()):
        pwm = max(raw_curve[power], max_pwm_so_far)
        monotonic_curve[power] = pwm
        max_pwm_so_far = pwm

    print(f"\n{'Power':<10} {'Raw PWM':<12} {'Monotonic PWM':<15}")
    print("-" * 40)
    for power in sorted(raw_curve.keys()):
        print(f"{power:>3}W       {raw_curve[power]:<12.0f} {monotonic_curve[power]:<15.0f}")

    # Generate code for fan controller
    print("\n" + "=" * 70)
    print("GENERATED CODE FOR ml-fan-control.py")
    print("=" * 70)

    # Power-based curve
    print("\n# Power → PWM curve (learned from historical data)")
    print("# Based on analysis: what PWM kept temps <= 85°C at each power level")
    print("POWER_PWM_POINTS = [")
    for power in sorted(monotonic_curve.keys()):
        pwm = int(monotonic_curve[power])
        print(f"    ({power}, {pwm}),")
    print("]")

    # Also generate a simplified version with key points
    print("\n# Simplified (key points only):")
    print("POWER_PWM_POINTS_SIMPLE = [")
    key_powers = [0, 50, 100, 150, 175, 200, 225, 250]
    for power in key_powers:
        # Find closest bucket
        bucket = (power // POWER_BUCKET_SIZE) * POWER_BUCKET_SIZE
        pwm = int(monotonic_curve.get(bucket, 255))
        print(f"    ({power}, {pwm}),  # {power}W")
    print("]")

    # Show the function that would use this
    print("\n# Add this function to ml-fan-control.py:")
    print("""
def get_power_based_pwm(self, max_power: int) -> int:
    \"\"\"Get PWM from power curve using linear interpolation.\"\"\"
    power = max(0, min(275, max_power))  # Clamp to valid range

    for i in range(len(POWER_PWM_POINTS) - 1):
        p1, pwm1 = POWER_PWM_POINTS[i]
        p2, pwm2 = POWER_PWM_POINTS[i + 1]

        if p1 <= power <= p2:
            if p2 == p1:
                return pwm1
            t = (power - p1) / (p2 - p1)
            return int(pwm1 + t * (pwm2 - pwm1))

    return POWER_PWM_POINTS[-1][1]
""")


def main():
    print("Loading data...")
    df = load_data(CSV_PATH)

    # Check if we have the new format with power
    if "max_power" not in df.columns or df["max_power"].isna().all():
        print("ERROR: CSV does not contain power data.")
        print("Make sure you're using the new CSV format with power columns.")
        return

    analyze_and_build_power_curve(df, TARGET_TEMP)


if __name__ == "__main__":
    main()
