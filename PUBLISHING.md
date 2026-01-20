# Publishing to Gitea NPM Registry

This guide explains how to publish the OpenCode Telemetry Plugin to your company's internal Gitea NPM registry.

## Prerequisites

1. **Gitea Access Token**
   - Go to your Gitea server: `https://gitea.company.com/user/settings/applications`
   - Click "Generate New Token"
   - Name: "npm-publish"
   - Select scopes: `write:package` (at minimum)
   - Copy the token (you won't see it again!)

2. **Organization/User**
   - Determine which Gitea organization or username will own the package
   - Example: `your-company` → `https://gitea.company.com/api/packages/your-company/npm/`

3. **Node.js/npm**
   - Ensure you have Node.js and npm installed
   - Run: `node -v` and `npm -v` to verify

---

## Quick Start (First-Time Setup)

### Step 1: Configure Registry

Run the interactive setup script:

```bash
make setup-registry
```

The script will ask for:
1. **Gitea server URL**: `https://gitea.company.com`
2. **Organization/username**: `your-company`
3. **Access token**: (paste the token you generated)

This will:
- Update `package.json` with correct URLs
- Configure npm to use your Gitea registry
- Create `.npmrc` with authentication

### Step 2: Test the Configuration

```bash
make publish-dry-run
```

This performs a dry-run publish to verify everything is configured correctly. Review the output for any errors.

### Step 3: Publish

```bash
make publish
```

This will prompt for confirmation, then publish the package to your Gitea registry.

---

## Manual Setup (Alternative)

If you prefer to configure manually:

### 1. Update package.json

Edit the `repository` and `publishConfig` sections:

```json
{
  "repository": {
    "type": "git",
    "url": "git+https://gitea.company.com/your-company/opencode-telemetry-plugin.git"
  },
  "publishConfig": {
    "registry": "https://gitea.company.com/api/packages/your-company/npm/"
  }
}
```

### 2. Configure npm

```bash
# Set the registry
npm config set registry https://gitea.company.com/api/packages/your-company/npm/

# Set the auth token
npm config set //gitea.company.com/api/packages/your-company/npm/:_authToken YOUR_TOKEN
```

### 3. Create .npmrc (Optional, for project-specific config)

Create `.npmrc` in the project root:

```
registry=https://gitea.company.com/api/packages/your-company/npm/
//gitea.company.com/api/packages/your-company/npm/:_authToken=YOUR_TOKEN
```

**Important:** `.npmrc` is already in `.gitignore` to prevent committing your token.

---

## Publishing Workflow

### First Release

```bash
# 1. Build the plugin
make build

# 2. Test the package
make publish-dry-run

# 3. Publish to registry
make publish
```

### Subsequent Releases

```bash
# 1. Make your changes to the code

# 2. Bump the version (choose one)
make version-patch   # 1.0.0 -> 1.0.1 (bug fixes)
make version-minor   # 1.0.0 -> 1.1.0 (new features)
make version-major   # 1.0.0 -> 2.0.0 (breaking changes)

# 3. Commit the version bump
git add package.json package-lock.json
git commit -m "chore: bump version to $(node -p "require('./package.json').version")"
git push

# 4. Publish to registry
make publish
```

---

## Version Management

### Semantic Versioning

Follow semantic versioning (semver):
- **Patch** (1.0.X): Bug fixes, no breaking changes
- **Minor** (1.X.0): New features, no breaking changes
- **Major** (X.0.0): Breaking changes

### Using Makefile Commands

```bash
# Patch version (1.0.0 -> 1.0.1)
make version-patch

# Minor version (1.0.0 -> 1.1.0)
make version-minor

# Major version (1.0.0 -> 2.0.0)
make version-major
```

These commands will:
1. Update `package.json` version
2. Create a git tag (e.g., `v1.0.1`)
3. Commit the change

### Manual Version Bump

```bash
# Alternatively, use npm directly
npm version patch   # or minor, or major
```

---

## Installing Published Package

Once published, users can install the package:

### Option 1: Configure Registry (Recommended)

Users need to configure npm to use your Gitea registry once:

```bash
npm config set registry https://gitea.company.com/api/packages/your-company/npm/
```

Then install normally:

```bash
npm install opencode-telemetry-plugin
```

### Option 2: Specify Registry Per-Install

```bash
npm install opencode-telemetry-plugin --registry https://gitea.company.com/api/packages/your-company/npm/
```

### Option 3: Use .npmrc in Project

Create `.npmrc` in the user's project:

```
registry=https://gitea.company.com/api/packages/your-company/npm/
```

Then install normally:

```bash
npm install opencode-telemetry-plugin
```

---

## For OpenCode Users

After the package is published, users can add it to their OpenCode config:

**`.opencode/opencode.jsonc`:**

```jsonc
{
  "plugins": [
    "opencode-telemetry-plugin"  // Will be installed from Gitea registry
  ],
  "experimental": {
    "openTelemetry": true
  }
}
```

OpenCode will automatically install the plugin using Bun/npm at startup.

---

## Troubleshooting

### Error: 401 Unauthorized

**Cause:** Invalid or expired access token.

**Solution:**
1. Generate a new token in Gitea
2. Run `make setup-registry` again, or
3. Update `.npmrc` manually with the new token

### Error: 404 Not Found

**Cause:** Incorrect registry URL or organization name.

**Solution:**
1. Verify the URL: `https://gitea.company.com/api/packages/YOUR_ORG/npm/`
2. Ensure the organization exists in Gitea
3. Run `make setup-registry` to reconfigure

### Error: Package already exists

**Cause:** You're trying to publish a version that already exists.

**Solution:**
1. Bump the version: `make version-patch` (or minor/major)
2. Then publish: `make publish`

### Error: Cannot read properties of undefined

**Cause:** `package.json` is malformed or missing required fields.

**Solution:**
1. Ensure `package.json` has `name`, `version`, `main`, `files` fields
2. Run `npm pack` locally to test packaging

---

## Package Contents

The published package includes:

```
opencode-telemetry-plugin/
├── dist/                    # Compiled JavaScript
│   ├── index.js
│   ├── index.d.ts
│   ├── metrics.js
│   ├── metrics.d.ts
│   └── ...
├── analyze_metrics.py       # Metrics analysis script
├── README.md               # Documentation
├── DISTRIBUTION.md         # Distribution guide
├── package.json            # Package metadata
└── LICENSE                 # License file
```

These files are specified in the `files` field of `package.json`.

---

## Security Best Practices

### 1. Protect Access Tokens

- **Never commit** `.npmrc` to git (already in `.gitignore`)
- **Never share** your personal access token
- **Rotate tokens** periodically
- **Use separate tokens** for CI/CD vs local development

### 2. Verify Package Contents

Before publishing, check what will be included:

```bash
npm pack --dry-run
```

Or:

```bash
make publish-dry-run
```

### 3. Code Signing (Optional)

For extra security, you can sign your packages:

```bash
npm publish --otp=123456
```

(Requires 2FA setup in Gitea/npm)

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Publish Package

on:
  release:
    types: [created]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - uses: actions/setup-node@v3
        with:
          node-version: '20'
          registry-url: 'https://gitea.company.com/api/packages/your-company/npm/'

      - run: npm ci
      - run: npm run build

      - run: npm publish
        env:
          NODE_AUTH_TOKEN: ${{ secrets.GITEA_NPM_TOKEN }}
```

### GitLab CI Example

```yaml
publish:
  stage: deploy
  only:
    - tags
  script:
    - npm ci
    - npm run build
    - echo "//gitea.company.com/api/packages/your-company/npm/:_authToken=${GITEA_NPM_TOKEN}" > .npmrc
    - npm publish
```

Store `GITEA_NPM_TOKEN` in CI/CD secrets.

---

## Useful Commands

```bash
# View current npm config
npm config list

# Check what will be published
npm pack --dry-run

# View published versions
npm view opencode-telemetry-plugin versions

# Check package info
npm info opencode-telemetry-plugin

# Unpublish a version (within 72 hours)
npm unpublish opencode-telemetry-plugin@1.0.0

# Deprecate a version
npm deprecate opencode-telemetry-plugin@1.0.0 "Use version 1.0.1 instead"
```

---

## Support

For issues related to:
- **Publishing**: Contact DevOps team
- **Plugin functionality**: Check the [README.md](README.md)
- **Gitea registry**: Check your Gitea server documentation

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `make setup-registry` | Configure Gitea npm registry (one-time) |
| `make publish-dry-run` | Test publish without actually publishing |
| `make publish` | Publish to registry |
| `make version-patch` | Bump patch version (1.0.X) |
| `make version-minor` | Bump minor version (1.X.0) |
| `make version-major` | Bump major version (X.0.0) |
| `npm config list` | View npm configuration |
| `npm view PKG versions` | List published versions |
