#!/bin/bash

# deploy-to-nfs.sh
# Deploy bundled OpenCode telemetry plugin to company NFS

set -e

# Configuration - update these values for your environment
NFS_PATH="${NFS_PATH:-/mnt/company-nfs/opencode-plugins}"
BUNDLE_FILE="telemetry-plugin.bundle.min.js"  # Use minified production bundle by default

echo "========================================="
echo "Deploy OpenCode Telemetry Plugin to NFS"
echo "========================================="
echo ""

# Build production bundle
echo "1. Building production bundle (minified)..."
npm run bundle -- --production
echo ""

# Verify bundle exists
echo "2. Verifying bundle..."
if [ ! -f "dist/$BUNDLE_FILE" ]; then
  echo "❌ Bundle not found: dist/$BUNDLE_FILE"
  exit 1
fi

BUNDLE_SIZE=$(du -h "dist/$BUNDLE_FILE" | cut -f1)
echo "   ✅ Bundle found: dist/$BUNDLE_FILE"
echo "   📦 Bundle size: $BUNDLE_SIZE"
echo ""

# Verify bundle syntax
echo "3. Checking bundle syntax..."
if ! node --check "dist/$BUNDLE_FILE"; then
  echo "❌ Bundle has syntax errors!"
  exit 1
fi
echo "   ✅ Bundle syntax is valid"
echo ""

# Check NFS mount
echo "4. Checking NFS mount..."
if [ ! -d "$NFS_PATH" ]; then
  echo "❌ NFS path not found: $NFS_PATH"
  echo ""
  echo "To test locally without NFS, you can:"
  echo "  1. Create a test directory: mkdir -p /tmp/test-nfs-plugin"
  echo "  2. Set NFS_PATH: export NFS_PATH=/tmp/test-nfs-plugin"
  echo "  3. Run this script again: ./deploy-to-nfs.sh"
  exit 1
fi
echo "   ✅ NFS mount accessible: $NFS_PATH"
echo ""

# Backup old version if it exists
if [ -f "$NFS_PATH/$BUNDLE_FILE" ]; then
  BACKUP_NAME="$BUNDLE_FILE.backup-$(date +%Y%m%d-%H%M%S)"
  echo "5. Backing up old version..."
  cp "$NFS_PATH/$BUNDLE_FILE" "$NFS_PATH/$BACKUP_NAME"
  echo "   ✅ Backup created: $BACKUP_NAME"
  echo ""
fi

# Copy new bundle
echo "6. Copying new bundle to NFS..."
cp "dist/$BUNDLE_FILE" "$NFS_PATH/"
echo "   ✅ Bundle copied to: $NFS_PATH/$BUNDLE_FILE"
echo ""

# Set permissions (readable by all)
chmod 644 "$NFS_PATH/$BUNDLE_FILE"
echo "7. Setting permissions (644 - readable by all)..."
ls -lh "$NFS_PATH/$BUNDLE_FILE"
echo ""

# Verify deployment
echo "8. Verifying deployment..."
if [ -f "$NFS_PATH/$BUNDLE_FILE" ]; then
  echo "   ✅ Deployment successful!"
  echo ""
  echo "========================================="
  echo "Deployment Complete!"
  echo "========================================="
  echo ""
  echo "Users can now configure OpenCode with:"
  echo ""
  echo '  {'
  echo "    \"plugin\": [\"file://$NFS_PATH/$BUNDLE_FILE\"],"
  echo '    "experimental": {'
  echo '      "openTelemetry": true'
  echo '    }'
  echo '  }'
  echo ""
  echo "To configure OTEL collector endpoint (optional):"
  echo '  export OTEL_EXPORTER_OTLP_ENDPOINT="http://otel-collector.company.com:4318"'
  echo '  export OTEL_EXPORTER_OTLP_PROTOCOL="http"'
  echo ""
else
  echo "❌ Deployment verification failed!"
  exit 1
fi
