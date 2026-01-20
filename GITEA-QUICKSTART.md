# Quick Start: Publishing to Gitea NPM Registry

This is a quick guide for publishing the OpenCode Telemetry Plugin to your company's Gitea NPM registry.

## TL;DR

```bash
# One-time setup
make setup-registry

# Publish
make publish
```

---

## Detailed Steps

### 1. Get Your Gitea Access Token

1. Go to: `https://your-gitea-server.com/user/settings/applications`
2. Click **"Generate New Token"**
3. Token name: `npm-publish`
4. Scopes: Check `write:package`
5. Click **"Generate Token"**
6. **Copy the token** (you won't see it again!)

### 2. Run Setup Script

```bash
cd /home/mtk26468/opencode-telemetry-plugin
make setup-registry
```

The script will ask:
- **Gitea URL**: `https://your-gitea-server.com`
- **Organization**: `your-company` (or your username)
- **Access Token**: (paste the token)

### 3. Test Configuration

```bash
make publish-dry-run
```

This simulates publishing without actually doing it. Check for errors.

### 4. Publish!

```bash
make publish
```

Confirm when prompted, and your package will be published!

---

## What Gets Configured?

The `make setup-registry` command:

1. **Updates `package.json`**:
   ```json
   {
     "repository": {
       "url": "git+https://your-gitea-server.com/your-org/opencode-telemetry-plugin.git"
     },
     "publishConfig": {
       "registry": "https://your-gitea-server.com/api/packages/your-org/npm/"
     }
   }
   ```

2. **Creates `.npmrc`** (local project config):
   ```
   registry=https://your-gitea-server.com/api/packages/your-org/npm/
   //your-gitea-server.com/api/packages/your-org/npm/:_authToken=YOUR_TOKEN
   ```

3. **Configures npm** globally to use your Gitea registry

---

## Publishing Updates

When you make changes and want to publish a new version:

```bash
# 1. Bump version (choose one)
make version-patch   # 1.0.0 -> 1.0.1 (bug fixes)
make version-minor   # 1.0.0 -> 1.1.0 (new features)
make version-major   # 1.0.0 -> 2.0.0 (breaking changes)

# 2. Publish
make publish
```

---

## For End Users (Installing the Package)

After you publish, your colleagues can install it:

### Step 1: Configure npm (one-time)

```bash
npm config set registry https://your-gitea-server.com/api/packages/your-org/npm/
```

### Step 2: Install

```bash
npm install opencode-telemetry-plugin
```

### Or add to OpenCode config

**`.opencode/opencode.jsonc`**:
```jsonc
{
  "plugins": ["opencode-telemetry-plugin"],
  "experimental": {
    "openTelemetry": true
  }
}
```

---

## Common Issues

### "401 Unauthorized"
- Your token is invalid or expired
- Generate a new token and run `make setup-registry` again

### "404 Not Found"
- Check the organization name is correct
- Verify the URL: `https://your-server.com/api/packages/YOUR_ORG/npm/`

### "Version already exists"
- You need to bump the version first
- Run: `make version-patch` then `make publish`

---

## All Available Commands

```bash
make help                  # Show all commands
make setup-registry        # Configure Gitea registry (one-time)
make build                 # Build the plugin
make publish-dry-run       # Test publish (safe, no actual publish)
make publish               # Publish to registry
make version-patch         # Bump patch version (1.0.X)
make version-minor         # Bump minor version (1.X.0)
make version-major         # Bump major version (X.0.0)
```

---

## Need More Details?

See [PUBLISHING.md](PUBLISHING.md) for comprehensive documentation.
