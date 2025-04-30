#!/bin/bash
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

PWM_PATH="/sys/class/hwmon/hwmon7/pwm3"
PWM_ENABLE_PATH="/sys/class/hwmon/hwmon7/pwm3_enable"

MIN_PWM=100
MAX_PWM=255

MIN_TEMP=30
MAX_TEMP=80

# Utilization threshold above which fan is aggressively bumped
UTIL_THRESH=80
BOOST_PWM=200

# Set fan to manual mode
echo 1 | tee $PWM_ENABLE_PATH

while true; do
    # Read GPU edge temp from sensors
    TEMP=$(sensors | awk '/edge:/ {print $2}' | sed 's/+//;s/\.0°C//')

    # Read GPU utilization
    UTIL=$(/usr/bin/rocm-smi --showuse | grep 'GPU use (%):' | awk -F': ' '{print $3}')

    # Fallback check
    if [ -z "$TEMP" ] || [ -z "$UTIL" ]; then
        echo "Warning: Unable to read GPU temp or utilization. Skipping..."
        sleep 10
        continue
    fi

    # Calculate PWM from temperature
    if (( TEMP <= MIN_TEMP )); then
        PWM=$MIN_PWM
    elif (( TEMP >= MAX_TEMP )); then
        PWM=$MAX_PWM
    else
        PWM=$(( ( (TEMP - MIN_TEMP) * (MAX_PWM - MIN_PWM) / (MAX_TEMP - MIN_TEMP) ) + MIN_PWM ))
    fi

    # Preemptively boost if GPU utilization is high
    if (( UTIL >= UTIL_THRESH && PWM < BOOST_PWM )); then
        echo "GPU util ${UTIL}% is high — boosting PWM to $BOOST_PWM"
        PWM=$BOOST_PWM
    fi

    echo "$PWM" | tee $PWM_PATH
    echo "GPU Temp: ${TEMP}°C, Util: ${UTIL}% -> Fan PWM: ${PWM}"

    sleep 10
done
