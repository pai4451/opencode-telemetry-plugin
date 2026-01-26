# Simplified Implementation: Environment Variables Only

## Summary

The plugin has been simplified to **only use environment variables** for configuration, removing all attempts to read custom config fields from `opencode.jsonc`.

## What Changed

### 1. Removed Custom Config Support

**Before:** Tried to read custom `telemetry` section from config file
```typescript
// ❌ This doesn't work - OpenCode strips custom fields
const userTelemetryConfig = configAny.experimental?.telemetry
```

**After:** Only uses environment variables
```typescript
// ✅ Environment variables bypass config schema
const metricsConfig = Config.parseMetricsConfig()  // No parameters
```

### 2. Simplified Config Parser

**File:** `src/config.ts`

**Before:**
- Accepted `userConfig` parameter
- Tried to read from config file first
- Had complex priority logic
- Included debug console.log statements

**After:**
- No parameters needed
- Only reads environment variables
- Simple and clear
- Clean code without debug statements

**Key functions:**
```typescript
export function parseMetricsConfig(): MetricsConfig
export function parseTracesConfig(): TracesConfig
```

### 3. Updated Plugin Entry Point

**File:** `src/index.ts`

**Before:**
```typescript
const userTelemetryConfig = configAny.experimental?.telemetry
const metricsConfig = Config.parseMetricsConfig(userTelemetryConfig)
```

**After:**
```typescript
// Parse configuration from environment variables only
const metricsConfig = Config.parseMetricsConfig()
```

Added helpful log message:
```typescript
Logger.log(`  Source: ${process.env.OTEL_EXPORTER_OTLP_ENDPOINT ? 'Environment variables' : 'Defaults'}`)
```

### 4. Removed Unnecessary Interfaces

**Removed:** `TelemetryConfig` interface (was for config file, no longer needed)

**Kept:** `MetricsConfig` and `TracesConfig` (still used internally)

## Why This Change?

OpenCode uses **Zod strict mode** for config validation:

```typescript
// From OpenCode source: packages/opencode/src/config/config.ts:1047
.strict()  // ← Rejects ALL unknown fields
```

The `experimental` schema **only** includes predefined fields:
- ✅ `openTelemetry` (boolean)
- ✅ `hook`
- ✅ `chatMaxRetries`
- ✅ `batch_tool`
- ❌ **NOT** `telemetry` (our custom field)

**Result:** Custom fields are **silently stripped** before reaching the plugin.

See `CONFIG_SCHEMA_INVESTIGATION.md` for full details and source code references.

## How to Use

### 1. Enable Plugin

Add to `~/.config/opencode/opencode.jsonc`:

```jsonc
{
  "experimental": {
    "openTelemetry": true
  }
}
```

**That's it!** Don't add a `telemetry` section - it won't work.

### 2. Use Defaults (No Config Needed)

If you're running with docker-compose locally:

```bash
docker-compose up -d
opencode  # Uses http://localhost:4318 automatically
```

### 3. Custom Configuration (Environment Variables)

**Option A: Set before running:**
```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="http://otel-collector:4318"
export OTEL_EXPORTER_OTLP_PROTOCOL="http"
opencode
```

**Option B: Use the provided script:**
```bash
./run-with-env.sh
```

**Option C: Add to shell profile (`~/.bashrc` or `~/.zshrc`):**
```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"
export OTEL_EXPORTER_OTLP_PROTOCOL="http"
```

## Environment Variables Supported

| Variable | Description | Default |
|----------|-------------|---------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Base endpoint (applies to both metrics and traces) | `http://localhost:4318` |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | Protocol: `http` or `grpc` | `http` |
| `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT` | Override for metrics only | Uses base endpoint |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | Override for traces only | Uses base endpoint |

These are **standard OpenTelemetry environment variables** - not custom!

## Verification

When OpenCode starts, check the logs:

```
[telemetry-plugin] Initializing metrics with config:
  Endpoint: http://localhost:4318
  Protocol: http
  Export interval: 5000ms
  Source: Environment variables  ← Check this line!
```

**Source values:**
- `Environment variables` - Using env vars ✅
- `Defaults` - Using built-in defaults

## Files Changed

| File | Change |
|------|--------|
| `src/config.ts` | Removed `userConfig` parameter, simplified to env vars only |
| `src/index.ts` | Removed config file parsing, added source logging |
| `README.md` | Updated configuration section |
| `CONFIGURATION_SIMPLE.md` | New simplified configuration guide |
| `run-with-env.sh` | Updated with clearer output |

## Files to Ignore

These files contain **outdated information** about config file support:

- ❌ `CONFIGURATION.md` - Describes config file usage (doesn't work)
- ❌ `config-example.jsonc` - Shows custom config (doesn't work)
- ❌ `CONFIG_LOCATIONS.md` - Describes multiple config files (not relevant)
- ❌ All project-level `opencode.jsonc` files with `telemetry` section (stripped by OpenCode)

**Use instead:**
- ✅ `CONFIGURATION_SIMPLE.md` - Environment variables only
- ✅ `CONFIG_SCHEMA_INVESTIGATION.md` - Why config files don't work
- ✅ `run-with-env.sh` - Example usage

## Testing

### Test with Defaults

```bash
# Clear logs
./view-logs.sh clear

# Start collector
cd /home/mtk26468/opencode && docker-compose up -d

# Run OpenCode (uses defaults)
opencode

# Check logs
./view-logs.sh | head -20
```

**Expected:** Should show `Source: Defaults`

### Test with Environment Variables

```bash
# Clear logs
./view-logs.sh clear

# Run with env vars
./run-with-env.sh

# Check logs
./view-logs.sh | head -20
```

**Expected:** Should show `Source: Environment variables`

## Benefits of This Approach

1. **✅ Simple** - No complex config parsing logic
2. **✅ Standard** - Uses OpenTelemetry standard env vars
3. **✅ Works** - Bypasses OpenCode schema limitations
4. **✅ Flexible** - Easy to change per environment
5. **✅ Documented** - Standard OTEL documentation applies
6. **✅ Clean** - Removed all non-working code

## Future Considerations

If OpenCode adds support for custom plugin config fields, we could:

1. Add back the `TelemetryConfig` interface
2. Update `parseMetricsConfig()` to accept optional parameter
3. Add priority: config file > env vars > defaults
4. Keep env var support for backward compatibility

But for now: **environment variables only**! ✅

## Documentation

- **CONFIGURATION_SIMPLE.md** - How to configure using env vars
- **CONFIG_SCHEMA_INVESTIGATION.md** - Why config files don't work
- **README.md** - Updated quick start guide
- **This file** - Implementation changes summary
