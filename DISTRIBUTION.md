# OpenCode Telemetry Plugin - Distribution Guide

This guide explains how to distribute the OpenCode Telemetry Plugin within your company without uploading to external npm registries.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Distribution Methods](#distribution-methods)
3. [Installation for End Users](#installation-for-end-users)
4. [Enterprise Deployment](#enterprise-deployment)

---

## Quick Start

### Building the Plugin

```bash
# Clean and build
make rebuild

# Or just build
make build
```

### Testing Locally

```bash
# Install to current project
make install

# Or install globally for all your projects
make install-global
```

---

## Distribution Methods

### Method 1: NPM Tarball (Recommended for Internal Distribution)

**Create the tarball:**
```bash
make pack
# Creates: opencode-telemetry-plugin-1.0.0.tgz
```

**Distribute the tarball:**
- Upload to internal file share
- Serve from internal web server
- Include in company software packages
- Commit to internal git repository

**End users install via:**
```bash
# From local file
npm install ./opencode-telemetry-plugin-1.0.0.tgz

# From internal web server
npm install https://internal-server.company.com/opencode-telemetry-plugin-1.0.0.tgz

# From git repository
npm install git+ssh://git@internal-git.company.com/plugins/opencode-telemetry-plugin.git
```

### Method 2: Private NPM Registry (Best for Large Organizations)

Set up an internal npm registry using:
- **Verdaccio** (lightweight, easy setup)
- **Nexus Repository** (enterprise-grade)
- **JFrog Artifactory** (enterprise-grade)
- **GitHub Packages** (if using GitHub Enterprise)

**Setup example with Verdaccio:**

```bash
# On your internal server
npm install -g verdaccio
verdaccio

# Configure registry (default: http://localhost:4873)
```

**Publish to private registry:**

```bash
# In plugin directory
npm set registry http://npm-registry.company.com:4873
npm publish
```

**End users configure:**

```bash
# Set company registry
npm set registry http://npm-registry.company.com:4873

# Or use .npmrc file
echo "registry=http://npm-registry.company.com:4873" > ~/.npmrc
```

**Install normally:**
```bash
npm install opencode-telemetry-plugin
```

### Method 3: Git Repository

**Host on internal git server:**

```bash
# Push to internal git
git remote add company git@internal-git.company.com:plugins/opencode-telemetry-plugin.git
git push company main
```

**End users install:**

```bash
# Via SSH
npm install git+ssh://git@internal-git.company.com/plugins/opencode-telemetry-plugin.git

# Via HTTPS
npm install git+https://internal-git.company.com/plugins/opencode-telemetry-plugin.git

# Specific version/tag
npm install git+ssh://git@internal-git.company.com/plugins/opencode-telemetry-plugin.git#v1.0.0
```

### Method 4: Direct Copy (Simple, No Package Manager)

**Package for distribution:**

```bash
make build
tar -czf opencode-telemetry-plugin.tar.gz dist/ package.json analyze_metrics.py README.md
```

**Distribute the tarball and include installation script:**

```bash
#!/bin/bash
# install-plugin.sh

PLUGIN_DIR="$HOME/.config/opencode/plugins/opencode-telemetry"

mkdir -p "$PLUGIN_DIR"
tar -xzf opencode-telemetry-plugin.tar.gz -C "$PLUGIN_DIR"

echo "Plugin installed to $PLUGIN_DIR"
echo "Add to your .opencode/opencode.jsonc:"
echo '  "plugins": ["opencode-telemetry"]'
```

---

## Installation for End Users

### Option 1: Using OpenCode Config (Automatic)

Add to `.opencode/opencode.jsonc`:

```jsonc
{
  "plugins": [
    // From npm tarball (local file)
    "./path/to/opencode-telemetry-plugin-1.0.0.tgz",

    // From internal npm registry
    "opencode-telemetry-plugin",

    // From git repository
    "git+ssh://git@internal-git.company.com/plugins/opencode-telemetry-plugin.git"
  ],
  "experimental": {
    "openTelemetry": true  // Enable OpenTelemetry
  }
}
```

OpenCode will automatically install the plugin using Bun at startup.

### Option 2: Manual Installation (Global)

```bash
# Install globally for all projects
mkdir -p ~/.config/opencode/plugins/opencode-telemetry

# Copy files
cp -r dist/* ~/.config/opencode/plugins/opencode-telemetry/
cp package.json ~/.config/opencode/plugins/opencode-telemetry/
cp analyze_metrics.py ~/.config/opencode/plugins/opencode-telemetry/
```

Then add to `.opencode/opencode.jsonc`:
```jsonc
{
  "plugins": ["opencode-telemetry"],
  "experimental": {
    "openTelemetry": true
  }
}
```

### Option 3: Manual Installation (Project-Level)

```bash
# Install to current project only
mkdir -p .opencode/plugin/opencode-telemetry

# Copy files
cp -r dist/* .opencode/plugin/opencode-telemetry/
cp package.json .opencode/plugin/opencode-telemetry/
cp analyze_metrics.py .opencode/plugin/opencode-telemetry/
```

Plugins in `.opencode/plugin/` are automatically loaded.

---

## Enterprise Deployment

### Automated Deployment via Configuration Management

**Ansible Playbook Example:**

```yaml
# deploy-opencode-plugin.yml
---
- name: Deploy OpenCode Telemetry Plugin
  hosts: developers
  tasks:
    - name: Create plugin directory
      file:
        path: "{{ ansible_env.HOME }}/.config/opencode/plugins/opencode-telemetry"
        state: directory
        mode: '0755'

    - name: Copy plugin files
      copy:
        src: opencode-telemetry-plugin/
        dest: "{{ ansible_env.HOME }}/.config/opencode/plugins/opencode-telemetry/"
        mode: '0644'

    - name: Create OpenCode config if not exists
      copy:
        content: |
          {
            "plugins": ["opencode-telemetry"],
            "experimental": {
              "openTelemetry": true
            }
          }
        dest: "{{ ansible_env.HOME }}/.opencode/opencode.jsonc"
        force: no
```

**Chef Recipe Example:**

```ruby
# recipes/opencode-telemetry.rb

directory "#{ENV['HOME']}/.config/opencode/plugins/opencode-telemetry" do
  recursive true
  action :create
end

remote_directory "#{ENV['HOME']}/.config/opencode/plugins/opencode-telemetry" do
  source 'opencode-telemetry-plugin'
  files_mode '0644'
  action :create
end
```

### Docker Image with Pre-installed Plugin

```dockerfile
# Dockerfile
FROM node:20-slim

# Install Bun
RUN curl -fsSL https://bun.sh/install | bash
ENV PATH="/root/.bun/bin:$PATH"

# Install OpenCode
RUN bun install -g @opencode-ai/cli

# Pre-install telemetry plugin
COPY opencode-telemetry-plugin-1.0.0.tgz /tmp/
RUN mkdir -p /root/.config/opencode/plugins/opencode-telemetry && \
    cd /root/.config/opencode/plugins/opencode-telemetry && \
    tar -xzf /tmp/opencode-telemetry-plugin-1.0.0.tgz --strip-components=1 && \
    rm /tmp/opencode-telemetry-plugin-1.0.0.tgz

# Default config
COPY opencode.jsonc /root/.opencode/opencode.jsonc

WORKDIR /workspace
CMD ["opencode"]
```

### Shared Network Drive Distribution

```bash
# Copy to shared drive
cp opencode-telemetry-plugin-1.0.0.tgz //file-server/shared/opencode-plugins/

# Users install from shared drive
npm install //file-server/shared/opencode-plugins/opencode-telemetry-plugin-1.0.0.tgz
```

---

## Verification

After installation, verify the plugin is loaded:

```bash
# Check OpenCode recognizes the plugin
opencode

# Look for log message:
# [opencode-telemetry] Plugin loaded. Logs: ~/.local/share/opencode/telemetry-plugin.log

# Check the log file
tail -f ~/.local/share/opencode/telemetry-plugin.log
```

---

## Updating the Plugin

### Version Management

1. Update version in `package.json`:
   ```json
   {
     "version": "1.1.0"
   }
   ```

2. Rebuild and redistribute:
   ```bash
   make pack
   # Creates: opencode-telemetry-plugin-1.1.0.tgz
   ```

3. Users update:
   ```bash
   npm update opencode-telemetry-plugin
   # Or reinstall from new tarball
   ```

---

## Troubleshooting

### Plugin not loading

1. Check OpenCode config:
   ```bash
   cat .opencode/opencode.jsonc
   ```

2. Check plugin directory exists:
   ```bash
   ls -la ~/.config/opencode/plugins/opencode-telemetry/
   # Or
   ls -la .opencode/plugin/opencode-telemetry/
   ```

3. Check OpenTelemetry is enabled:
   ```jsonc
   {
     "experimental": {
       "openTelemetry": true  // Must be true
     }
   }
   ```

### Dependencies not installed

OpenCode uses Bun to install dependencies. Ensure `package.json` includes all dependencies:

```json
{
  "dependencies": {
    "@opentelemetry/api": "^1.9.0",
    // ... other dependencies
  }
}
```

---

## Security Considerations

- **Code Signing**: Sign tarballs for verification
- **Checksum Verification**: Provide SHA256 checksums
- **Access Control**: Restrict registry/repository access to authorized users
- **Audit Trail**: Log plugin installations via configuration management

### Example Checksum Verification

```bash
# Generate checksum
sha256sum opencode-telemetry-plugin-1.0.0.tgz > opencode-telemetry-plugin-1.0.0.tgz.sha256

# Verify before installation
sha256sum -c opencode-telemetry-plugin-1.0.0.tgz.sha256
```

---

## Support

For internal support:
- Documentation: [Internal Wiki Link]
- Issues: [Internal Issue Tracker]
- Contact: [DevOps Team Email]
