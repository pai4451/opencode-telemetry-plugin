#!/bin/bash
# Setup script for configuring Gitea npm registry
# Usage: ./setup-registry.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "======================================"
echo "  Gitea NPM Registry Setup"
echo "======================================"
echo ""

# Get Gitea server URL
echo -e "${YELLOW}Enter your Gitea server URL (e.g., https://gitea.company.com):${NC}"
read -p "> " GITEA_URL

# Remove trailing slash if present
GITEA_URL=${GITEA_URL%/}

# Get organization/user name
echo ""
echo -e "${YELLOW}Enter your Gitea organization or username (where the package will be published):${NC}"
read -p "> " GITEA_ORG

# Get authentication token
echo ""
echo -e "${YELLOW}Enter your Gitea access token:${NC}"
echo "(Generate one at: ${GITEA_URL}/user/settings/applications)"
read -s -p "> " GITEA_TOKEN
echo ""

# Construct registry URL
REGISTRY_URL="${GITEA_URL}/api/packages/${GITEA_ORG}/npm/"

echo ""
echo "======================================"
echo "  Configuration Summary"
echo "======================================"
echo "Gitea URL:    ${GITEA_URL}"
echo "Organization: ${GITEA_ORG}"
echo "Registry URL: ${REGISTRY_URL}"
echo ""

# Confirm
echo -e "${YELLOW}Continue with this configuration? (y/n)${NC}"
read -p "> " CONFIRM

if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo -e "${RED}Setup cancelled.${NC}"
    exit 1
fi

echo ""
echo "======================================"
echo "  Configuring..."
echo "======================================"

# Update package.json
echo "1. Updating package.json..."

# Create temporary file with updated package.json
TEMP_FILE=$(mktemp)

# Update repository URL
REPO_URL="git+${GITEA_URL}/${GITEA_ORG}/opencode-telemetry-plugin.git"

# Use jq if available, otherwise use sed
if command -v jq &> /dev/null; then
    jq --arg repo "$REPO_URL" --arg registry "$REGISTRY_URL" \
       '.repository.url = $repo | .publishConfig.registry = $registry' \
       package.json > "$TEMP_FILE"
    mv "$TEMP_FILE" package.json
else
    # Fallback to sed
    sed -i.bak "s|https://your-gitea-server.com/your-org/opencode-telemetry-plugin.git|${REPO_URL}|g" package.json
    sed -i.bak "s|https://your-gitea-server.com/api/packages/your-org/npm/|${REGISTRY_URL}|g" package.json
    rm -f package.json.bak
fi

echo -e "   ${GREEN}✓${NC} package.json updated"

# Configure npm to use the registry
echo "2. Configuring npm registry..."

# Set registry for this package scope (if using scoped package)
npm config set registry "${REGISTRY_URL}"

echo -e "   ${GREEN}✓${NC} npm registry configured"

# Configure authentication
echo "3. Configuring authentication..."

# Extract hostname from registry URL for .npmrc
REGISTRY_HOST=$(echo "${REGISTRY_URL}" | sed -E 's|https?://([^/]+).*|\1|')

# Set auth token in .npmrc
npm config set "//${REGISTRY_HOST}/api/packages/${GITEA_ORG}/npm/:_authToken" "${GITEA_TOKEN}"

echo -e "   ${GREEN}✓${NC} Authentication configured"

# Create .npmrc in project directory (optional, for project-specific config)
echo "4. Creating project .npmrc file..."

cat > .npmrc <<EOF
registry=${REGISTRY_URL}
//${REGISTRY_HOST}/api/packages/${GITEA_ORG}/npm/:_authToken=${GITEA_TOKEN}
EOF

echo -e "   ${GREEN}✓${NC} .npmrc file created"

echo ""
echo "======================================"
echo -e "  ${GREEN}Setup Complete!${NC}"
echo "======================================"
echo ""
echo "Next steps:"
echo "  1. Build the package:  make build"
echo "  2. Test publish:       make publish-dry-run"
echo "  3. Publish:            make publish"
echo ""
echo "Or use npm directly:"
echo "  npm publish"
echo ""
echo -e "${YELLOW}Note: The .npmrc file contains your auth token.${NC}"
echo -e "${YELLOW}      Make sure it's in .gitignore (already done).${NC}"
echo ""
