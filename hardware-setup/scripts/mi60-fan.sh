#!/bin/bash
# GPU Fan Control Script for Dual MI60 with 120mm Fan Duct
# See: https://www.thingiverse.com/thing:7203670
#
# This script is optimized for a 120mm fan blowing through a custom duct
# that covers both MI60 GPUs. Adjust MIN_PWM and temperature thresholds
# if using different cooling hardware.

export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Dynamically find the hwmon path for the nct6798 fan controller
for hwmon in /sys/class/hwmon/hwmon*; do
    if [[ -f "$hwmon/name" ]] && grep -q "nct6798" "$hwmon/name"; then
        HWMON_PATH="$hwmon"
        break
    fi
done

if [[ -z "$HWMON_PATH" ]]; then
    echo "Error: nct6798 not found. Is nct6775 loaded?"
    exit 1
fi

PWM_PATH="$HWMON_PATH/pwm3"
PWM_ENABLE_PATH="$HWMON_PATH/pwm3_enable"

# Fan control thresholds (using junction temps)
# Optimized for 120mm fan - quieter operation
MIN_PWM=110      # Minimum PWM (fan stall threshold)
MAX_PWM=255      # Maximum PWM (diminishing returns above this)
MIN_TEMP=50      # Start ramping at this junction temp
MAX_TEMP=90      # Reach MAX_PWM at this junction temp
UTIL_THRESH=80   # Utilization threshold for boost
BOOST_PWM=190    # Boost PWM when util is high

# Logging
LOG_FILE="/var/log/gpu-fan-control.csv"
if [[ ! -f "$LOG_FILE" ]]; then
    echo "timestamp,gpu0_junction,gpu0_util,gpu1_junction,gpu1_util,max_temp,max_util,pwm" > "$LOG_FILE"
fi

# Ensure the fan is in manual mode
echo 1 > "$PWM_ENABLE_PATH"

while true; do
    # Get junction temps from both GPUs
    TEMPS=($(/usr/bin/rocm-smi --showtemp | grep -Po 'GPU\[.\].*junction.*:\s*\K[0-9]+'))
    # Get GPU utilizations
    UTILS=($(/usr/bin/rocm-smi --showuse | grep -Po 'GPU use.*:\s*\K[0-9]+'))

    if [[ ${#TEMPS[@]} -lt 2 || ${#UTILS[@]} -lt 2 ]]; then
        echo "Warning: Failed to read temps or utils for both GPUs."
        sleep 3
        continue
    fi

    # Capture both GPU values explicitly
    TEMP0=${TEMPS[0]}
    TEMP1=${TEMPS[1]}
    UTIL0=${UTILS[0]}
    UTIL1=${UTILS[1]}

    # Use maximum values for fan logic
    TEMP=$(( TEMP0 > TEMP1 ? TEMP0 : TEMP1 ))
    UTIL=$(( UTIL0 > UTIL1 ? UTIL0 : UTIL1 ))

    # Calculate PWM based on temp
    if (( TEMP <= MIN_TEMP )); then
        PWM=$MIN_PWM
    elif (( TEMP >= MAX_TEMP )); then
        PWM=$MAX_PWM
    else
        PWM=$(( MIN_PWM + (MAX_PWM - MIN_PWM) * (TEMP - MIN_TEMP) / (MAX_TEMP - MIN_TEMP) ))
    fi

    # Boost if utilization is high
    if (( UTIL >= UTIL_THRESH && TEMP >= 65 && PWM < BOOST_PWM )); then
        echo "Util ${UTIL}% is high — boosting PWM to $BOOST_PWM"
        PWM=$BOOST_PWM
    fi

    # Rate limit PWM changes (max ±15 per cycle) to prevent audible spikes
    CURRENT_PWM=$(cat "$PWM_PATH")
    if (( PWM > CURRENT_PWM + 15 )); then
        PWM=$((CURRENT_PWM + 15))
    elif (( PWM < CURRENT_PWM - 15 )); then
        PWM=$((CURRENT_PWM - 15))
    fi

    # Emergency bypass: skip rate limiting at high temps
    if (( TEMP >= 80 )); then
        PWM=$(( MIN_PWM + (MAX_PWM - MIN_PWM) * (TEMP - MIN_TEMP) / (MAX_TEMP - MIN_TEMP) ))
    fi

    # Write fan speed
    echo "$PWM" > "$PWM_PATH"

    # Log to CSV
    echo "$(date -Iseconds),$TEMP0,$UTIL0,$TEMP1,$UTIL1,$TEMP,$UTIL,$PWM" >> "$LOG_FILE"

    # Log to stdout (journalctl)
    echo "GPU0: ${TEMP0}°C, Util: ${UTIL0}% | GPU1: ${TEMP1}°C, Util: ${UTIL1}% → Max Temp: ${TEMP}°C, Max Util: ${UTIL}% → PWM: ${PWM}"

    sleep 2
done
