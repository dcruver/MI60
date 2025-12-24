#!/usr/bin/env python3
"""
Build a Utilization → PWM Curve from Historical Fan Control Data.

This script analyzes the CSV log from gpu-fan-control to determine what PWM values
actually kept temperatures safe at each GPU utilization level. The output is a
monotonic curve that can be pasted into ml-fan-control.py.

METHODOLOGY:
1. Load all samples from /var/log/gpu-fan-control.csv
2. Filter to "safe" samples where max_temp <= TARGET_TEMP
3. For each 10% utilization bucket, find the median PWM of safe samples
4. Enforce monotonicity: higher utilization never gets lower PWM
5. Output the curve in a format ready for ml-fan-control.py

WHY THIS WORKS:
Traditional ML approaches (predicting temperature from features) failed because they
learned correlation, not causation. High PWM correlated with high temps in our data
because the old reactive controller only went to max PWM AFTER temps spiked.

This approach sidesteps that problem: we don't predict anything. We just ask
"what PWM values actually worked?" and use those directly.

USAGE:
    python train_pwm_curve.py

After running, copy the UTIL_PWM_POINTS output into ml-fan-control.py and restart
the service. You should do this after collecting several weeks of operational data
with your specific cooling setup.
"""

import pandas as pd
import numpy as np
from pathlib import Path

CSV_PATH = "/var/log/gpu-fan-control.csv"
TARGET_TEMP = 85.0


def load_data(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(
        csv_path,
        names=["timestamp", "gpu0_temp", "gpu0_util", "gpu1_temp", "gpu1_util",
               "max_temp", "max_util", "pwm"],
        parse_dates=["timestamp"],
    )
    return df


def analyze_and_build_curve(df: pd.DataFrame, target_temp: float):
    """
    Build a monotonic PWM curve from utilization.

    For each utilization bucket:
    1. Find all samples where temp stayed safe
    2. Determine the minimum PWM that achieved this reliably (75th percentile)
    3. Enforce monotonicity (higher util never gets lower PWM)
    """

    print(f"Building curve for target temp: {target_temp}°C")
    print(f"Total samples: {len(df):,}")

    # Filter to safe samples
    safe_df = df[df["max_temp"] <= target_temp].copy()
    print(f"Safe samples: {len(safe_df):,}")

    # Analyze by utilization bucket (10% increments)
    results = []

    print(f"\n{'Util':<8} {'Safe Samples':<15} {'Avg Temp':<10} {'PWM p25':<10} {'PWM p50':<10} {'PWM p75':<10}")
    print("-" * 70)

    for util in range(0, 101, 10):
        util_low = util
        util_high = util + 10

        # All samples in this util range
        all_mask = (df["max_util"] >= util_low) & (df["max_util"] < util_high)
        all_samples = df[all_mask]

        # Safe samples in this util range
        safe_mask = (safe_df["max_util"] >= util_low) & (safe_df["max_util"] < util_high)
        safe_samples = safe_df[safe_mask]

        if len(safe_samples) < 10:
            pwm_p25 = pwm_p50 = pwm_p75 = 255
            avg_temp = 0
        else:
            pwm_p25 = safe_samples["pwm"].quantile(0.25)
            pwm_p50 = safe_samples["pwm"].quantile(0.50)
            pwm_p75 = safe_samples["pwm"].quantile(0.75)
            avg_temp = safe_samples["max_temp"].mean()

        results.append({
            "util": util,
            "safe_count": len(safe_samples),
            "total_count": len(all_samples),
            "avg_temp": avg_temp,
            "pwm_p25": pwm_p25,
            "pwm_p50": pwm_p50,
            "pwm_p75": pwm_p75,
        })

        print(f"{util}-{util_high}%   {len(safe_samples):<15} {avg_temp:<10.1f} {pwm_p25:<10.0f} {pwm_p50:<10.0f} {pwm_p75:<10.0f}")

    # Build monotonic curve using p50 (median of safe samples)
    print("\n=== Building Monotonic Curve ===")

    # Start with raw values
    raw_curve = {r["util"]: r["pwm_p50"] for r in results}

    # Enforce monotonicity: each higher util level must have >= PWM
    monotonic_curve = {}
    max_pwm_so_far = 110

    for util in sorted(raw_curve.keys()):
        pwm = max(raw_curve[util], max_pwm_so_far)
        monotonic_curve[util] = pwm
        max_pwm_so_far = pwm

    print(f"\n{'Util':<8} {'Raw PWM':<12} {'Monotonic PWM':<15}")
    print("-" * 35)
    for util in sorted(raw_curve.keys()):
        print(f"{util}%      {raw_curve[util]:<12.0f} {monotonic_curve[util]:<15.0f}")

    # Generate code for fan controller
    print("\n=== Generated Curve for Fan Controller ===\n")

    # Simplify to key points
    key_utils = [0, 20, 40, 60, 80, 90, 100]
    simplified = []

    for util in key_utils:
        # Find closest bucket
        bucket = (util // 10) * 10
        pwm = monotonic_curve.get(bucket, 255)
        simplified.append((util, int(pwm)))

    # Remove redundant entries and create threshold-based curve
    print("UTIL_PWM_CURVE = [")
    prev_pwm = None
    for util, pwm in reversed(simplified):
        if pwm != prev_pwm:
            print(f"    ({util}, {pwm}),  # >= {util}% util")
            prev_pwm = pwm
    print("]")

    # Also show as interpolation points for smoother curve
    print("\n# Or for linear interpolation:")
    print("UTIL_PWM_POINTS = [")
    for util in range(0, 101, 10):
        pwm = monotonic_curve.get(util, 255)
        print(f"    ({util}, {int(pwm)}),")
    print("]")


def main():
    print("Loading data...")
    df = load_data(CSV_PATH)

    analyze_and_build_curve(df, TARGET_TEMP)


if __name__ == "__main__":
    main()
