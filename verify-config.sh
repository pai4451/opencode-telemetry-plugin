#!/bin/bash

# verify-config.sh
# Verify that both OpenCode configs are using the bundled plugin

echo "========================================="
echo "OpenCode Telemetry Plugin - Config Verification"
echo "========================================="
echo ""

BUNDLE_PATH="/home/mtk26468/opencode-telemetry-plugin/dist/telemetry-plugin.bundle.js"
GLOBAL_CONFIG="$HOME/.config/opencode/opencode.jsonc"
PROJECT_CONFIG="/home/mtk26468/opencode/.opencode/opencode.jsonc"

# Check if bundle exists
echo "1. Checking bundle file..."
if [ -f "$BUNDLE_PATH" ]; then
  BUNDLE_SIZE=$(du -h "$BUNDLE_PATH" | cut -f1)
  echo "   ✅ Bundle exists: $BUNDLE_PATH"
  echo "   📦 Size: $BUNDLE_SIZE"
else
  echo "   ❌ Bundle not found: $BUNDLE_PATH"
  echo "   Run: npm run bundle"
  exit 1
fi
echo ""

# Check global config
echo "2. Checking global config..."
if [ -f "$GLOBAL_CONFIG" ]; then
  if grep -q "telemetry-plugin.bundle.js" "$GLOBAL_CONFIG"; then
    echo "   ✅ Global config using bundled plugin"
    grep "plugin" "$GLOBAL_CONFIG" | head -2
  else
    echo "   ⚠️  Global config NOT using bundled plugin"
    grep "plugin" "$GLOBAL_CONFIG" | head -2
  fi
else
  echo "   ⚠️  Global config not found: $GLOBAL_CONFIG"
fi
echo ""

# Check project config
echo "3. Checking project config..."
if [ -f "$PROJECT_CONFIG" ]; then
  if grep -q "telemetry-plugin.bundle.js" "$PROJECT_CONFIG"; then
    echo "   ⚠️  Project config has plugin (should be global only)"
    grep "plugin" "$PROJECT_CONFIG" | head -2
  else
    echo "   ✅ Project config does NOT have plugin (using global config)"
    grep -B 1 -A 1 "Plugin configured globally" "$PROJECT_CONFIG" 2>/dev/null || echo "   (Plugin removed from project config)"
  fi
else
  echo "   ⚠️  Project config not found: $PROJECT_CONFIG"
fi
echo ""

# Check if openTelemetry is enabled
echo "4. Checking OpenTelemetry flag..."
if grep -q '"openTelemetry": true' "$GLOBAL_CONFIG" 2>/dev/null; then
  echo "   ✅ Global config has openTelemetry enabled"
else
  echo "   ⚠️  Global config missing openTelemetry flag"
fi

if grep -q '"openTelemetry": true' "$PROJECT_CONFIG" 2>/dev/null; then
  echo "   ✅ Project config has openTelemetry enabled"
else
  echo "   ℹ️  Project config doesn't set openTelemetry (using global)"
fi
echo ""

# Summary
echo "========================================="
echo "Summary"
echo "========================================="
echo ""
echo "Bundle path:"
echo "  $BUNDLE_PATH"
echo ""
echo "To rebuild bundle with latest changes:"
echo "  cd /home/mtk26468/opencode-telemetry-plugin"
echo "  npm run bundle"
echo ""
echo "To test:"
echo "  cat /home/mtk26468/opencode/steps.md"
echo ""
