#!/bin/bash
# Create DMG installer for Weather Trader

set -e

echo "=== Creating DMG Installer ==="
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

APP_NAME="WeatherTrader"
DMG_NAME="WeatherTrader-1.0.0"
VOLUME_NAME="Weather Trader"

# Check if app exists
if [ ! -d "dist/$APP_NAME.app" ]; then
    echo "Error: dist/$APP_NAME.app not found. Run build_macos.sh first."
    exit 1
fi

# Create temporary directory for DMG contents
DMG_TEMP="dmg_temp"
rm -rf "$DMG_TEMP"
mkdir -p "$DMG_TEMP"

# Copy app to temp directory
cp -R "dist/$APP_NAME.app" "$DMG_TEMP/"

# Create Applications symlink
ln -s /Applications "$DMG_TEMP/Applications"

# Create README
cat > "$DMG_TEMP/README.txt" << 'EOF'
Weather Trader Installation
===========================

1. Drag WeatherTrader.app to the Applications folder
2. Launch from Applications
3. On first launch, you may need to right-click and select "Open"
   to bypass Gatekeeper (since the app is not notarized)

Requirements:
- macOS 12.0 (Monterey) or later
- Internet connection for market data

For support, visit: https://github.com/weathertrader/app
EOF

# Create DMG
echo "Creating DMG..."
hdiutil create -volname "$VOLUME_NAME" \
    -srcfolder "$DMG_TEMP" \
    -ov -format UDZO \
    "dist/$DMG_NAME.dmg"

# Cleanup
rm -rf "$DMG_TEMP"

echo ""
echo "DMG created: dist/$DMG_NAME.dmg"
echo ""
echo "To distribute:"
echo "1. Test the DMG on a clean macOS system"
echo "2. (Optional) Sign with: codesign --deep --force --verify --verbose --sign 'Developer ID' dist/$DMG_NAME.dmg"
echo "3. (Optional) Notarize with Apple for Gatekeeper approval"
