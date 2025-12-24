#!/bin/bash
# Install data-driven GPU fan control for dual MI60
#
# This controller uses a utilization→PWM curve learned from 300k+ historical
# samples. Unlike reactive temperature-based control, it preemptively ramps
# the fan based on GPU utilization - preventing temperature spikes before
# they occur.
#
# Results: Junction temps reduced from 96-97°C to 80°C max, significantly
# extending GPU lifespan.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/gpu-fan-control"

echo "=== Installing Data-Driven GPU Fan Control ==="
echo ""
echo "This controller uses a learned utilization→PWM curve to keep your"
echo "MI60 GPUs running cool. Expect junction temps around 80°C instead"
echo "of the 95°C+ spikes from reactive control."
echo ""

# Stop existing service
echo "Stopping gpu-fan-control.service..."
systemctl stop gpu-fan-control.service || true

# Create install directory
echo "Creating $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"

# Copy files
echo "Copying files..."
cp "$SCRIPT_DIR/ml-fan-control.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/train_pwm_curve.py" "$INSTALL_DIR/"

# Create venv and install dependencies
echo "Setting up Python virtual environment..."
python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install --quiet pandas numpy

# Install service file
echo "Installing systemd service..."
cp "$SCRIPT_DIR/ml-fan-control.service" /etc/systemd/system/gpu-fan-control.service
systemctl daemon-reload

# Start service
echo "Starting gpu-fan-control.service..."
systemctl start gpu-fan-control.service
systemctl enable gpu-fan-control.service

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Your MI60 GPUs are now protected by preemptive fan control."
echo ""
echo "Monitor with: journalctl -fu gpu-fan-control.service"
echo "View logs:    tail -f /var/log/gpu-fan-control.csv"
echo ""
echo "To rebuild the PWM curve from your own data (after weeks of operation):"
echo "  cd $INSTALL_DIR"
echo "  sudo .venv/bin/python train_pwm_curve.py"
echo "  # Then update UTIL_PWM_POINTS in ml-fan-control.py with the output"
echo "  sudo systemctl restart gpu-fan-control.service"
