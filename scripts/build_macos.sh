#!/bin/bash
# Build script for Weather Trader macOS application

set -e

echo "=== Weather Trader macOS Build Script ==="
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "1. Creating virtual environment..."
python3 -m venv build_venv
source build_venv/bin/activate

echo "2. Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
pip install py2app

echo "3. Building frontend..."
cd frontend
npm install
npm run build
cd ..

echo "4. Building macOS application..."
python macos/setup.py py2app

echo "5. Build complete!"
echo ""
echo "Application bundle created at: dist/WeatherTrader.app"
echo ""
echo "To run:"
echo "  open dist/WeatherTrader.app"
echo ""
echo "To create DMG installer, run:"
echo "  ./scripts/create_dmg.sh"

# Cleanup
deactivate
rm -rf build_venv
