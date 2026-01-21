#!/usr/bin/env python3
"""
Temperature-Based GPU Fan Control for Dual AMD Instinct MI60 with Push-Pull Cooling.

This controller uses TEMPERATURE as the primary driver (not power/utilization) to
minimize fan noise while maintaining safe junction temperatures.

KEY INSIGHT: GPU thermal mass means power bursts don't instantly raise temperature.
The old utilization-based approach ramped fans to 100% on every burst, even though
temps stayed cool. By controlling on TEMP instead, we allow short bursts without
noise, only ramping fans when temps actually start rising.

HOW IT WORKS:
1. Temperature-based PWM curves for intake (120mm) and exhaust (92mm) fans
2. Exhaust fan runs lower PWM since it's louder
3. Trend detection: if temp rising fast (>2°C/interval), boost fans preemptively
4. Emergency mode at 90°C - both fans to max

DUAL FAN SETUP:
- Intake: 120mm fan (pwm3) - primary cooling, quieter
- Exhaust: 92mm fan (pwm1) - secondary, louder, runs at lower PWM

Data analysis showed bursts are <5s and temps actually DROP during them with high
PWM. This confirms we were over-cooling. Now we let thermal mass absorb short
bursts and only ramp fans when needed.
"""

import subprocess
import re
import time
import sys
from collections import deque
from pathlib import Path
from datetime import datetime

# Force line-buffered stdout for real-time logging under systemd
sys.stdout.reconfigure(line_buffering=True)

# Configuration
LOG_FILE = Path("/var/log/gpu-fan-control.csv")

# Adaptive polling - now ultra-fast with sysfs reads (~0.08ms overhead)
POLL_INTERVAL_CRITICAL = 0.05  # 20Hz when util >= 90% or temp >= 80°C
POLL_INTERVAL_NORMAL = 0.1     # 10Hz otherwise

# Temperature targets
EMERGENCY_TEMP = 90.0  # Above this, go to max PWM immediately
MIN_TEMP = 50.0        # Below this, use minimum PWM (quiet mode)

# PWM limits
MIN_PWM = 110
MAX_PWM = 255

# Temperature → PWM curve (temp-based control for noise reduction)
# Key insight: thermal mass means power bursts don't instantly raise temp.
# Control on TEMP, not power, to avoid unnecessary fan noise on short bursts.
# Exhaust fan is louder, so we keep it lower when possible.
TEMP_INTAKE_POINTS = [
    (50, 110),   # Cool - minimum reliable speed
    (65, 170),   # Moderate - some cooling needed
    (75, 210),   # Warm - ramping up
    (82, 230),   # Hot - working hard
    (90, 255),   # Emergency threshold
]

TEMP_EXHAUST_POINTS = [
    (50, 110),   # Cool - minimum reliable speed
    (65, 140),   # Moderate
    (75, 180),   # Warm
    (82, 220),   # Hot
    (90, 255),   # Emergency
]

# Rate limiting (scaled by poll interval)
MAX_PWM_CHANGE_PER_SEC = 10  # Max change per second (except emergency)

# Exploration mode configuration
EXPLORE_MODE = "--explore" in sys.argv
EXPLORE_HOLD_TIME = 30.0  # Seconds to hold each exhaust PWM level
EXPLORE_EXHAUST_LEVELS = [110, 130, 150, 170, 190, 210, 230, 255]  # PWM levels to test
EXPLORE_TEMP_CEILING = 85  # If we hit this, abort exploration and go to max


def find_hwmon_path() -> str:
    """Find the hwmon path for nct6798 fan controller."""
    for hwmon in Path("/sys/class/hwmon").iterdir():
        name_file = hwmon / "name"
        if name_file.exists() and "nct6798" in name_file.read_text():
            return str(hwmon)
    raise RuntimeError("nct6798 not found. Is nct6775 loaded?")


# GPU sysfs paths (direct reads are ~100x faster than rocm-smi subprocess)
GPU_SYSFS = [
    {
        "temp": Path("/sys/class/drm/card1/device/hwmon/hwmon2/temp2_input"),  # junction
        "util": Path("/sys/class/drm/card1/device/gpu_busy_percent"),
        "power": Path("/sys/class/drm/card1/device/hwmon/hwmon2/power1_input"),  # microwatts
    },
    {
        "temp": Path("/sys/class/drm/card2/device/hwmon/hwmon3/temp2_input"),  # junction
        "util": Path("/sys/class/drm/card2/device/gpu_busy_percent"),
        "power": Path("/sys/class/drm/card2/device/hwmon/hwmon3/power1_input"),  # microwatts
    },
]


def get_gpu_stats() -> tuple[list[int], list[int], list[int]]:
    """Get junction temps, utilization, and power via direct sysfs reads."""
    temps = []
    utils = []
    powers = []
    for gpu in GPU_SYSFS:
        # Temp is in millidegrees (84000 = 84°C)
        temp = int(gpu["temp"].read_text().strip()) // 1000
        util = int(gpu["util"].read_text().strip())
        # Power is in microwatts (180000000 = 180W)
        power = int(gpu["power"].read_text().strip()) // 1000000
        temps.append(temp)
        utils.append(util)
        powers.append(power)
    return temps, utils, powers


class FanController:
    def __init__(self):
        # History buffers (kept for potential future use)
        self.temp_history = deque(maxlen=10)
        self.pwm_history = deque(maxlen=10)
        self.util_history = deque(maxlen=10)

        # Find hwmon
        self.hwmon_path = find_hwmon_path()

        # Fan paths: intake (120mm on pwm3) and exhaust (92mm on pwm1)
        self.intake_pwm_path = Path(self.hwmon_path) / "pwm3"
        self.intake_enable_path = Path(self.hwmon_path) / "pwm3_enable"
        self.exhaust_pwm_path = Path(self.hwmon_path) / "pwm1"
        self.exhaust_enable_path = Path(self.hwmon_path) / "pwm1_enable"
        self.exhaust_min_pwm = 150  # Minimum for exhaust fan

        # Current state
        self.current_intake_pwm = MIN_PWM
        self.current_exhaust_pwm = self.exhaust_min_pwm

        # Exploration state
        self.explore_exhaust_idx = len(EXPLORE_EXHAUST_LEVELS) - 1  # Start at max
        self.explore_start_time = None
        self.explore_samples = []  # Collect samples during exploration
        self.explore_load_bucket = None  # Track if load changes significantly

        # Initialize log (only if we can write to it)
        try:
            if not LOG_FILE.exists():
                with open(LOG_FILE, "w") as f:
                    f.write("timestamp,gpu0_junction,gpu0_util,gpu0_power,gpu1_junction,gpu1_util,gpu1_power,"
                            "max_temp,max_util,max_power,intake_pwm,exhaust_pwm\n")
        except PermissionError:
            print(f"Warning: Cannot write to {LOG_FILE}, logging to stdout only")

    def enable_manual_mode(self):
        """Set both fans to manual PWM control."""
        self.intake_enable_path.write_text("1")
        self.exhaust_enable_path.write_text("1")

    def set_pwm(self, intake_pwm: int, exhaust_pwm: int = None):
        """Write PWM values to both fans."""
        # Ensure intake PWM is within valid range
        intake_pwm = int(max(MIN_PWM, min(MAX_PWM, intake_pwm)))
        # If exhaust not specified, use intake with floor
        if exhaust_pwm is None:
            exhaust_pwm = max(self.exhaust_min_pwm, intake_pwm)
        else:
            exhaust_pwm = int(max(MIN_PWM, min(MAX_PWM, exhaust_pwm)))
        # Set both fans
        self.intake_pwm_path.write_text(str(intake_pwm))
        self.exhaust_pwm_path.write_text(str(exhaust_pwm))
        self.current_intake_pwm = intake_pwm
        self.current_exhaust_pwm = exhaust_pwm

    def get_current_pwm(self) -> tuple[int, int]:
        """Read current PWM values from both fans."""
        intake = int(self.intake_pwm_path.read_text().strip())
        exhaust = int(self.exhaust_pwm_path.read_text().strip())
        return intake, exhaust

    def get_temp_based_pwm(self, temp: int, points: list[tuple[int, int]]) -> int:
        """Get PWM from temperature curve using linear interpolation."""
        # Below minimum temp - use lowest PWM
        if temp <= points[0][0]:
            return points[0][1]

        # Above maximum temp - use highest PWM
        if temp >= points[-1][0]:
            return points[-1][1]

        # Find the right segment and interpolate
        for i in range(len(points) - 1):
            t1, p1 = points[i]
            t2, p2 = points[i + 1]

            if t1 <= temp <= t2:
                # Linear interpolation
                if t2 == t1:
                    return p1
                frac = (temp - t1) / (t2 - t1)
                return int(p1 + frac * (p2 - p1))

        # Fallback
        return points[-1][1]

    def find_optimal_pwm(self, temps: list[int], utils: list[int]) -> tuple[int, int, str]:
        """
        Find optimal PWM using TEMPERATURE as primary driver (not utilization).

        Key insight: thermal mass means power bursts don't instantly raise temp.
        By controlling on temp instead of power/util, we avoid unnecessary fan
        noise during short bursts while still protecting against sustained loads.

        Returns: (intake_pwm, exhaust_pwm, driver)
        """
        max_temp = max(temps)

        # Emergency: too hot
        if max_temp >= EMERGENCY_TEMP:
            return MAX_PWM, MAX_PWM, "emergency"

        # Check for rapid temperature rise - boost fans preemptively
        # Note: 5°C threshold avoids triggering on normal batch-to-batch variation (74→83°C)
        temp_trend = self.get_temp_trend()
        if temp_trend > 5.0:  # Rising more than 5°C per reading interval
            # Temp climbing fast - preemptive boost
            trend_boost = min(30, int(temp_trend * 5))
            intake_pwm = min(MAX_PWM, self.current_intake_pwm + trend_boost)
            exhaust_pwm = min(MAX_PWM, self.current_exhaust_pwm + trend_boost)
            return intake_pwm, exhaust_pwm, "trend"

        # Get temperature-based PWM for both fans
        intake_pwm = self.get_temp_based_pwm(max_temp, TEMP_INTAKE_POINTS)
        exhaust_pwm = self.get_temp_based_pwm(max_temp, TEMP_EXHAUST_POINTS)

        return intake_pwm, exhaust_pwm, "temp"

    def get_poll_interval(self, max_util: int, max_temp: int) -> float:
        """Get poll interval based on current utilization and temperature."""
        # Fast polling when under heavy load OR when temps are elevated
        if max_util >= 90 or max_temp >= 80:
            return POLL_INTERVAL_CRITICAL
        return POLL_INTERVAL_NORMAL

    def get_temp_trend(self) -> float:
        """Calculate temperature trend (°C/sec) from recent history."""
        if len(self.temp_history) < 3:
            return 0.0
        # Compare last 3 readings
        recent = list(self.temp_history)[-3:]
        return (recent[-1] - recent[0]) / (len(recent) - 1)

    def explore_exhaust(self, temps: list[int], utils: list[int], powers: list[int], intake_pwm: int) -> tuple[int, str]:
        """
        Exploration mode: systematically test exhaust PWM levels.

        Strategy:
        - Keep intake at the learned curve value
        - Cycle through exhaust levels from high to low
        - Hold each level for EXPLORE_HOLD_TIME seconds
        - If temp exceeds ceiling, retreat to max and reset
        - Record outcomes for ML training

        Returns: (exhaust_pwm, driver_string)
        """
        max_temp = max(temps)
        max_util = max(utils)
        max_power = max(powers)
        now = time.time()

        # Safety: if too hot, retreat to max exhaust
        if max_temp >= EXPLORE_TEMP_CEILING:
            print(f"EXPLORE: Temp {max_temp}°C hit ceiling, retreating to max exhaust")
            self.explore_exhaust_idx = len(EXPLORE_EXHAUST_LEVELS) - 1
            self.explore_start_time = None
            return MAX_PWM, "explore-retreat"

        # Check if load changed significantly (restart exploration)
        current_load_bucket = max_power // 50  # 50W buckets
        if self.explore_load_bucket is not None and current_load_bucket != self.explore_load_bucket:
            print(f"EXPLORE: Load changed ({self.explore_load_bucket*50}W -> {current_load_bucket*50}W), restarting")
            self.explore_exhaust_idx = len(EXPLORE_EXHAUST_LEVELS) - 1
            self.explore_start_time = None
        self.explore_load_bucket = current_load_bucket

        # Only explore during significant load
        if max_util < 50:
            return EXPLORE_EXHAUST_LEVELS[-1], "explore-idle"

        # Start exploration timer if not set
        if self.explore_start_time is None:
            self.explore_start_time = now
            print(f"EXPLORE: Starting exhaust test at PWM {EXPLORE_EXHAUST_LEVELS[self.explore_exhaust_idx]}")

        # Check if we've held current level long enough
        elapsed = now - self.explore_start_time
        if elapsed >= EXPLORE_HOLD_TIME:
            # Record results for this level
            exhaust_pwm = EXPLORE_EXHAUST_LEVELS[self.explore_exhaust_idx]
            avg_temp = sum(self.temp_history) / len(self.temp_history) if self.temp_history else max_temp
            print(f"EXPLORE: Exhaust {exhaust_pwm} at ~{max_power}W: avg_temp={avg_temp:.1f}°C, max_temp={max_temp}°C")

            # Move to next lower exhaust level
            if self.explore_exhaust_idx > 0:
                self.explore_exhaust_idx -= 1
                self.explore_start_time = now
                print(f"EXPLORE: Trying exhaust PWM {EXPLORE_EXHAUST_LEVELS[self.explore_exhaust_idx]}")
            else:
                # Completed all levels, restart from high
                print("EXPLORE: Completed full sweep, restarting from max")
                self.explore_exhaust_idx = len(EXPLORE_EXHAUST_LEVELS) - 1
                self.explore_start_time = now

        return EXPLORE_EXHAUST_LEVELS[self.explore_exhaust_idx], "explore"

    def apply_rate_limit(self, target_pwm: int, current_pwm: int, poll_interval: float, emergency: bool = False) -> int:
        """Apply rate limiting to PWM decreases only - increases are instant."""
        if emergency:
            return target_pwm

        # Allow instant ramp UP (no rate limiting)
        if target_pwm >= current_pwm:
            return target_pwm

        # Rate limit ramp DOWN to prevent fan noise oscillation
        max_decrease = int(MAX_PWM_CHANGE_PER_SEC * poll_interval)
        max_decrease = max(max_decrease, 5)
        if target_pwm < current_pwm - max_decrease:
            return current_pwm - max_decrease
        return target_pwm

    def update_history(self, max_temp: int, max_util: int, pwm: int):
        """Update history buffers."""
        self.temp_history.append(max_temp)
        self.util_history.append(max_util)
        self.pwm_history.append(pwm)

    def log(self, temps: list[int], utils: list[int], powers: list[int], intake_pwm: int, exhaust_pwm: int, driver: str):
        """Log to CSV and stdout."""
        timestamp = datetime.now().isoformat()
        max_temp = max(temps)
        max_util = max(utils)
        max_power = max(powers)

        # CSV
        try:
            with open(LOG_FILE, "a") as f:
                f.write(f"{timestamp},{temps[0]},{utils[0]},{powers[0]},{temps[1]},{utils[1]},{powers[1]},"
                        f"{max_temp},{max_util},{max_power},{intake_pwm},{exhaust_pwm}\n")
        except PermissionError:
            pass

        # Stdout
        print(f"GPU0: {temps[0]}°C/{utils[0]}%/{powers[0]}W | GPU1: {temps[1]}°C/{utils[1]}%/{powers[1]}W → "
              f"In:{intake_pwm}/Ex:{exhaust_pwm} ({driver})")

    def run(self):
        """Main control loop."""
        print(f"GPU Fan Controller starting (TEMP-BASED MODE)...")
        if EXPLORE_MODE:
            print(f"  *** EXPLORATION MODE ENABLED ***")
            print(f"  Testing exhaust PWM levels: {EXPLORE_EXHAUST_LEVELS}")
            print(f"  Hold time per level: {EXPLORE_HOLD_TIME}s")
        print(f"  Temp curve (intake): {TEMP_INTAKE_POINTS}")
        print(f"  Temp curve (exhaust): {TEMP_EXHAUST_POINTS}")
        print(f"  Emergency temp: {EMERGENCY_TEMP}°C")
        print(f"  Polling: {POLL_INTERVAL_CRITICAL}s (hot) / {POLL_INTERVAL_NORMAL}s (normal)")
        print()

        self.enable_manual_mode()

        # Warm up history
        print("Warming up history buffer...")
        for _ in range(5):
            try:
                temps, utils, powers = get_gpu_stats()
                intake_pwm, _ = self.get_current_pwm()
                self.update_history(max(temps), max(utils), intake_pwm)
                time.sleep(POLL_INTERVAL_NORMAL)
            except Exception as e:
                print(f"Warning: {e}")
                time.sleep(POLL_INTERVAL_NORMAL)

        print("Starting control loop...")
        poll_interval = POLL_INTERVAL_NORMAL
        while True:
            try:
                temps, utils, powers = get_gpu_stats()

                if len(temps) < 2 or len(utils) < 2:
                    print("Warning: Failed to read stats for both GPUs")
                    time.sleep(poll_interval)
                    continue

                max_util = max(utils)

                # Find optimal PWM for both fans (temp-based)
                target_intake, target_exhaust, driver = self.find_optimal_pwm(temps, utils)

                # Apply rate limiting (skip for emergency)
                emergency = driver == "emergency"
                intake_pwm = self.apply_rate_limit(target_intake, self.current_intake_pwm, poll_interval, emergency)
                exhaust_pwm = self.apply_rate_limit(target_exhaust, self.current_exhaust_pwm, poll_interval, emergency)

                # Exploration mode overrides exhaust
                if EXPLORE_MODE:
                    exhaust_pwm, explore_driver = self.explore_exhaust(temps, utils, powers, intake_pwm)
                    driver = explore_driver

                # Set both fans
                self.set_pwm(intake_pwm, exhaust_pwm)

                # Update history
                self.update_history(max(temps), max_util, intake_pwm)

                # Log both fan PWM values
                self.log(temps, utils, powers, self.current_intake_pwm, self.current_exhaust_pwm, driver)

                # Adaptive poll interval for next iteration
                poll_interval = self.get_poll_interval(max_util, max(temps))

            except Exception as e:
                print(f"Error: {e}")

            time.sleep(poll_interval)


def main():
    controller = FanController()
    controller.run()


if __name__ == "__main__":
    main()
