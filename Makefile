# Makefile for OpenCode Telemetry Plugin
# ========================================

.PHONY: all build clean install install-global test help pack

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
	@echo "Distribution:"
	@echo "  make pack          - Create npm tarball for distribution"
	@echo ""
	@echo "For more info, see DISTRIBUTION.md"
