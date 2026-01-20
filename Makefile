# Makefile for OpenCode Telemetry Plugin
# ========================================

.PHONY: all build clean install install-global test help pack publish publish-dry-run setup-registry version-patch version-minor version-major

# Default target
all: build

# Build the plugin
build:
	@echo "Building plugin..."
	npm run build
	@echo "✓ Build complete"

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	rm -rf dist/
	rm -f *.js *.d.ts *.js.map
	rm -f ./*.tgz
	@echo "✓ Clean complete"

# Full rebuild
rebuild: clean build

# Install plugin locally for current project
install: build
	@echo "Installing plugin to current project..."
	mkdir -p .opencode/plugin/opencode-telemetry
	cp -r dist/* .opencode/plugin/opencode-telemetry/
	cp package.json .opencode/plugin/opencode-telemetry/
	cp analyze_metrics.py .opencode/plugin/opencode-telemetry/
	@echo "✓ Plugin installed to .opencode/plugin/opencode-telemetry/"

# Install plugin globally for all projects
install-global: build
	@echo "Installing plugin globally..."
	mkdir -p ~/.config/opencode/plugins/opencode-telemetry
	cp -r dist/* ~/.config/opencode/plugins/opencode-telemetry/
	cp package.json ~/.config/opencode/plugins/opencode-telemetry/
	cp analyze_metrics.py ~/.config/opencode/plugins/opencode-telemetry/
	@echo "✓ Plugin installed globally to ~/.config/opencode/plugins/opencode-telemetry/"

# Create npm package tarball for distribution
pack: build
	@echo "Creating distributable package..."
	npm pack
	@echo "✓ Package created: opencode-telemetry-plugin-1.0.0.tgz"
	@echo ""
	@echo "To install from tarball:"
	@echo "  npm install ./opencode-telemetry-plugin-1.0.0.tgz"

# Setup Gitea npm registry (interactive)
setup-registry:
	@echo "Setting up Gitea npm registry..."
	@./setup-registry.sh

# Publish to npm registry (dry-run)
publish-dry-run: build
	@echo "Running publish dry-run (no actual publish)..."
	npm publish --dry-run
	@echo ""
	@echo "✓ Dry-run complete. Review the output above."
	@echo "  If everything looks good, run: make publish"

# Publish to npm registry
publish: build
	@echo "Publishing to npm registry..."
	@echo ""
	@echo "⚠️  This will publish the package to the configured registry."
	@echo "   Current version: $$(node -p "require('./package.json').version")"
	@echo "   Registry: $$(npm config get registry)"
	@echo ""
	@read -p "Continue? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		npm publish; \
		echo ""; \
		echo "✓ Package published successfully!"; \
		echo ""; \
		echo "Users can install with:"; \
		echo "  npm install opencode-telemetry-plugin"; \
	else \
		echo "Publish cancelled."; \
		exit 1; \
	fi

# Bump patch version (1.0.0 -> 1.0.1)
version-patch:
	@echo "Bumping patch version..."
	npm version patch
	@echo "✓ Version bumped to $$(node -p "require('./package.json').version")"

# Bump minor version (1.0.0 -> 1.1.0)
version-minor:
	@echo "Bumping minor version..."
	npm version minor
	@echo "✓ Version bumped to $$(node -p "require('./package.json').version")"

# Bump major version (1.0.0 -> 2.0.0)
version-major:
	@echo "Bumping major version..."
	npm version major
	@echo "✓ Version bumped to $$(node -p "require('./package.json').version")"

# Uninstall from current project
uninstall:
	@echo "Uninstalling plugin from current project..."
	rm -rf .opencode/plugin/opencode-telemetry
	@echo "✓ Plugin uninstalled from current project"

# Uninstall from global config
uninstall-global:
	@echo "Uninstalling plugin globally..."
	rm -rf ~/.config/opencode/plugins/opencode-telemetry
	@echo "✓ Plugin uninstalled globally"

# Run type checking
typecheck:
	@echo "Running type check..."
	npx tsc --noEmit
	@echo "✓ Type check passed"

# Watch mode for development
dev:
	@echo "Starting development mode (watch)..."
	npm run dev

# Display help
help:
	@echo "OpenCode Telemetry Plugin - Build Targets"
	@echo "=========================================="
	@echo ""
	@echo "Development:"
	@echo "  make build         - Build the plugin"
	@echo "  make clean         - Remove build artifacts"
	@echo "  make rebuild       - Clean and build"
	@echo "  make dev           - Start watch mode for development"
	@echo "  make typecheck     - Run TypeScript type checking"
	@echo ""
	@echo "Installation:"
	@echo "  make install       - Install to current project (.opencode/plugin/)"
	@echo "  make install-global - Install globally (~/.config/opencode/plugins/)"
	@echo "  make uninstall     - Uninstall from current project"
	@echo "  make uninstall-global - Uninstall globally"
	@echo ""
	@echo "Publishing (Gitea NPM Registry):"
	@echo "  make setup-registry    - Configure Gitea npm registry (one-time setup)"
	@echo "  make publish-dry-run   - Test publish without actually publishing"
	@echo "  make publish           - Publish to configured npm registry"
	@echo "  make version-patch     - Bump patch version (1.0.0 -> 1.0.1)"
	@echo "  make version-minor     - Bump minor version (1.0.0 -> 1.1.0)"
	@echo "  make version-major     - Bump major version (1.0.0 -> 2.0.0)"
	@echo ""
	@echo "Distribution:"
	@echo "  make pack          - Create npm tarball for distribution"
	@echo ""
	@echo "For more info, see DISTRIBUTION.md"
