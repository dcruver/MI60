#!/bin/bash
# Install ML-based GPU fan control, replacing the bash script version
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/gpu-fan-control"

echo "=== Installing ML-based GPU Fan Control ==="

# Stop existing service
echo "Stopping gpu-fan-control.service..."
systemctl stop gpu-fan-control.service || true

# Create install directory
echo "Creating $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"

# Copy files
echo "Copying files..."
cp "$SCRIPT_DIR/ml-fan-control.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/train_fan_model_v2.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/fan_model.pkl" "$INSTALL_DIR/"

# Create venv and install dependencies
echo "Setting up Python virtual environment..."
python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install --quiet pandas scikit-learn

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
echo "Monitor with: journalctl -fu gpu-fan-control.service"
echo ""
echo "To retrain the model later:"
echo "  cd $INSTALL_DIR"
echo "  .venv/bin/python train_fan_model_v2.py"
