#!/bin/bash
# Script to copy files to Raspberry Pi Pico
# Make sure your Pico is connected via USB before running this script

set -e  # Exit on error

echo "=========================================="
echo "Copying files to Raspberry Pi Pico"
echo "=========================================="
echo ""

# Check if device is available
echo "Checking for connected Pico..."
if ! mpremote connect auto run -c "import sys; print('Connected')" > /dev/null 2>&1; then
    echo "ERROR: No Pico detected!"
    echo ""
    echo "Please ensure:"
    echo "  1. Your Raspberry Pi Pico is connected via USB"
    echo "  2. The Pico is in the correct mode (not in bootloader mode)"
    echo "  3. You have the correct USB drivers installed"
    echo ""
    echo "You can check available devices with: mpremote connect list"
    exit 1
fi

echo "Pico detected! Starting file transfer..."
echo ""

# Copy main files
echo "[1/5] Copying main.py..."
mpremote connect auto cp main.py :main.py

# Copy library files
echo "[2/5] Copying lib/bme280.py..."
mpremote connect auto cp lib/bme280.py :lib/bme280.py

echo "[3/5] Copying lib/config.py..."
mpremote connect auto cp lib/config.py :lib/config.py

echo "[4/5] Copying lib/__init__.py..."
mpremote connect auto cp lib/__init__.py :lib/__init__.py

echo "[5/5] Copying boot.py..."
mpremote connect auto cp boot.py :boot.py

echo ""
echo "=========================================="
echo "✓ Files copied successfully!"
echo "=========================================="
echo ""
echo "The Pico will automatically restart and run the updated code."
echo "Monitor the output with: mpremote connect auto"
