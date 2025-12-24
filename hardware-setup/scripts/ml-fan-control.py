#!/usr/bin/env python3
"""
Data-Driven GPU Fan Control for Dual AMD Instinct MI60.

This controller extends GPU lifespan by keeping junction temperatures at 80°C instead
of the 96-97°C spikes seen with reactive (temperature-based) fan control.

KEY INSIGHT: Reactive control always loses. By the time temperature spikes, the GPU's
thermal mass means you're playing catch-up for seconds. This controller is PREEMPTIVE:
it ramps fan speed based on GPU utilization, not temperature. When a workload starts,
the fan ramps up immediately - before temperatures have time to rise.

HOW IT WORKS:
1. The UTIL_PWM_POINTS curve was learned by analyzing 300,000+ historical samples
2. For each utilization level, we found what PWM values actually kept temps safe
3. Linear interpolation provides smooth transitions between points
4. Temperature monitoring remains as a safety backstop

RESULTS:
- Junction temps: 80°C max (was 96-97°C)
- Fan behavior: Smooth curves, max ~88% (was spiking to 100%)
- GPU longevity: Significantly extended by reducing thermal stress

To rebuild the curve for your setup, run train_pwm_curve.py after collecting data.
"""

import subprocess
import re
import time
import sys
from collections import deque
from pathlib import Path
from datetime import datetime

# Configuration
LOG_FILE = Path("/var/log/gpu-fan-control.csv")

# Adaptive polling
POLL_INTERVAL_CRITICAL = 0.5  # When util >= 90%
POLL_INTERVAL_NORMAL = 1      # Everything else

# Temperature targets
TARGET_TEMP = 82.0   # Try to stay at or below this
MAX_TEMP = 92.0      # Hard limit - go to max PWM above this
MIN_TEMP = 50.0      # Below this, use minimum PWM

# PWM limits
MIN_PWM = 110
MAX_PWM = 255
PWM_CANDIDATES = [110, 130, 150, 170, 190, 210, 230, 255]

# Utilization → PWM curve (learned from historical data)
# Based on analysis of 300k samples: what PWM kept temps <= 85°C at each util level
# Uses linear interpolation for smooth fan response
UTIL_PWM_POINTS = [
    (0, 110),
    (10, 122),
    (20, 126),
    (30, 189),
    (40, 207),
    (50, 207),
    (60, 211),
    (70, 219),
    (80, 224),
    (90, 225),
    (100, 225),
]

# Rate limiting (scaled by poll interval)
MAX_PWM_CHANGE_PER_SEC = 10  # Max change per second (except emergency)


def find_hwmon_path() -> str:
    """Find the hwmon path for nct6798 fan controller."""
    for hwmon in Path("/sys/class/hwmon").iterdir():
        name_file = hwmon / "name"
        if name_file.exists() and "nct6798" in name_file.read_text():
            return str(hwmon)
    raise RuntimeError("nct6798 not found. Is nct6775 loaded?")


def get_gpu_stats() -> tuple[list[int], list[int]]:
    """Get junction temps and utilization from rocm-smi."""
    # Get temps
    temp_output = subprocess.check_output(
        ["/usr/bin/rocm-smi", "--showtemp"],
        text=True
    )
    temps = [int(x) for x in re.findall(r'GPU\[.\].*junction.*:\s*(\d+)', temp_output)]

    # Get utilization
    util_output = subprocess.check_output(
        ["/usr/bin/rocm-smi", "--showuse"],
        text=True
    )
    utils = [int(x) for x in re.findall(r'GPU use.*:\s*(\d+)', util_output)]

    return temps, utils


class FanController:
    def __init__(self):
        # History buffers (kept for potential future use)
        self.temp_history = deque(maxlen=10)
        self.pwm_history = deque(maxlen=10)
        self.util_history = deque(maxlen=10)

        # Find hwmon
        self.hwmon_path = find_hwmon_path()
        self.pwm_path = Path(self.hwmon_path) / "pwm3"
        self.pwm_enable_path = Path(self.hwmon_path) / "pwm3_enable"

        # Current state
        self.current_pwm = MIN_PWM

        # Initialize log (only if we can write to it)
        # Use same format as bash script for compatibility
        try:
            if not LOG_FILE.exists():
                with open(LOG_FILE, "w") as f:
                    f.write("timestamp,gpu0_junction,gpu0_util,gpu1_junction,gpu1_util,"
                            "max_temp,max_util,pwm\n")
        except PermissionError:
            print(f"Warning: Cannot write to {LOG_FILE}, logging to stdout only")

    def enable_manual_mode(self):
        """Set fan to manual PWM control."""
        self.pwm_enable_path.write_text("1")

    def set_pwm(self, pwm: int):
        """Write PWM value to fan controller."""
        # Ensure PWM is an integer within valid range
        pwm = int(max(MIN_PWM, min(MAX_PWM, pwm)))
        self.pwm_path.write_text(str(pwm))
        self.current_pwm = pwm

    def get_current_pwm(self) -> int:
        """Read current PWM value."""
        return int(self.pwm_path.read_text().strip())

    def get_util_based_pwm(self, max_util: int) -> int:
        """Get PWM from utilization curve using linear interpolation."""
        # Clamp utilization
        util = max(0, min(100, max_util))

        # Find surrounding points for interpolation
        for i in range(len(UTIL_PWM_POINTS) - 1):
            u1, p1 = UTIL_PWM_POINTS[i]
            u2, p2 = UTIL_PWM_POINTS[i + 1]

            if u1 <= util <= u2:
                # Linear interpolation
                if u2 == u1:
                    return p1
                t = (util - u1) / (u2 - u1)
                return int(p1 + t * (p2 - p1))

        # Fallback to last point
        return UTIL_PWM_POINTS[-1][1]

    def find_optimal_pwm(self, temps: list[int], utils: list[int]) -> tuple[int, float, str]:
        """
        Find optimal PWM using utilization curve as primary driver.

        Returns: (pwm, predicted_delta, driver)
        """
        max_temp = max(temps)
        max_util = max(utils)

        # Emergency: already too hot
        if max_temp >= MAX_TEMP:
            return MAX_PWM, 0.0, "emergency"

        # Get utilization-based PWM (preemptive)
        util_pwm = self.get_util_based_pwm(max_util)

        # Get temperature-based PWM (reactive safety net)
        if max_temp <= MIN_TEMP:
            temp_pwm = MIN_PWM
        elif max_temp >= TARGET_TEMP:
            # Linear ramp from TARGET_TEMP to MAX_TEMP
            temp_pwm = int(MIN_PWM + (MAX_PWM - MIN_PWM) * (max_temp - MIN_TEMP) / (MAX_TEMP - MIN_TEMP))
        else:
            temp_pwm = MIN_PWM

        # Use the higher of util-based or temp-based
        if util_pwm >= temp_pwm:
            return util_pwm, 0.0, "util"
        else:
            return temp_pwm, 0.0, "temp"

    def get_poll_interval(self, max_util: int) -> float:
        """Get poll interval based on current utilization."""
        if max_util >= 90:
            return POLL_INTERVAL_CRITICAL
        return POLL_INTERVAL_NORMAL

    def apply_rate_limit(self, target_pwm: int, poll_interval: float, emergency: bool = False) -> int:
        """Apply rate limiting to PWM decreases only - increases are instant."""
        if emergency:
            return target_pwm

        current = self.get_current_pwm()

        # Allow instant ramp UP (no rate limiting)
        if target_pwm >= current:
            return target_pwm

        # Rate limit ramp DOWN to prevent fan noise oscillation
        max_decrease = int(MAX_PWM_CHANGE_PER_SEC * poll_interval)
        max_decrease = max(max_decrease, 5)
        if target_pwm < current - max_decrease:
            return current - max_decrease
        return target_pwm

    def update_history(self, max_temp: int, max_util: int, pwm: int):
        """Update history buffers."""
        self.temp_history.append(max_temp)
        self.util_history.append(max_util)
        self.pwm_history.append(pwm)

    def log(self, temps: list[int], utils: list[int], pwm: int, pred_delta: float, driver: str):
        """Log to CSV and stdout."""
        timestamp = datetime.now().isoformat()
        max_temp = max(temps)
        max_util = max(utils)

        # CSV (same format as bash script for compatibility)
        try:
            with open(LOG_FILE, "a") as f:
                f.write(f"{timestamp},{temps[0]},{utils[0]},{temps[1]},{utils[1]},"
                        f"{max_temp},{max_util},{pwm}\n")
        except PermissionError:
            pass

        # Stdout
        print(f"GPU0: {temps[0]}°C/{utils[0]}% | GPU1: {temps[1]}°C/{utils[1]}% → "
              f"PWM: {pwm} ({driver})")

    def run(self):
        """Main control loop."""
        print(f"GPU Fan Controller starting...")
        print(f"  Curve: 0%→{UTIL_PWM_POINTS[0][1]}, 30%→{UTIL_PWM_POINTS[3][1]}, 60%→{UTIL_PWM_POINTS[6][1]}, 100%→{UTIL_PWM_POINTS[-1][1]} (interpolated)")
        print(f"  Target temp: {TARGET_TEMP}°C, Emergency: {MAX_TEMP}°C")
        print(f"  Polling: {POLL_INTERVAL_CRITICAL}s (≥90% util) / {POLL_INTERVAL_NORMAL}s (otherwise)")
        print()

        self.enable_manual_mode()

        # Warm up history
        print("Warming up history buffer...")
        for _ in range(5):
            try:
                temps, utils = get_gpu_stats()
                self.update_history(max(temps), max(utils), self.get_current_pwm())
                time.sleep(POLL_INTERVAL_NORMAL)
            except Exception as e:
                print(f"Warning: {e}")
                time.sleep(POLL_INTERVAL_NORMAL)

        print("Starting control loop...")
        poll_interval = POLL_INTERVAL_NORMAL
        while True:
            try:
                temps, utils = get_gpu_stats()

                if len(temps) < 2 or len(utils) < 2:
                    print("Warning: Failed to read stats for both GPUs")
                    time.sleep(poll_interval)
                    continue

                max_util = max(utils)

                # Find optimal PWM
                target_pwm, pred_delta, driver = self.find_optimal_pwm(temps, utils)

                # Apply rate limiting (skip for emergency)
                emergency = driver == "emergency"
                pwm = self.apply_rate_limit(target_pwm, poll_interval, emergency)

                # Set PWM
                self.set_pwm(pwm)

                # Update history
                self.update_history(max(temps), max_util, pwm)

                # Log
                self.log(temps, utils, pwm, pred_delta, driver)

                # Adaptive poll interval for next iteration
                poll_interval = self.get_poll_interval(max_util)

            except Exception as e:
                print(f"Error: {e}")

            time.sleep(poll_interval)


def main():
    controller = FanController()
    controller.run()


if __name__ == "__main__":
    main()
