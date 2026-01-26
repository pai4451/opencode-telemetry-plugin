# HTTP Path Fix - Root Cause Analysis

## The Problem

The JSONL files (metrics.jsonl and traces.jsonl) remained **empty** even though:
- ✅ Plugin initialized successfully
- ✅ Plugin collected telemetry data (visible in logs)
- ✅ OTEL collector was running
- ✅ Configuration looked correct

## Root Cause

**HTTP and gRPC use different URL formats for OTLP exporters!**

### gRPC Protocol
Uses **base URL** without paths:
```
http://localhost:4317
```
The gRPC protocol handles routing internally via RPC calls.

### HTTP Protocol
Requires **full URL with OTLP paths**:
```
http://localhost:4318/v1/metrics  ← For metrics
http://localhost:4318/v1/traces   ← For traces
```

## What We Were Doing Wrong

**Before the fix:**
```typescript
// Config parser returned:
endpoint: "http://localhost:4318"  // ❌ Missing /v1/metrics path!
protocol: "http"

// Exporter tried to send to:
http://localhost:4318  // ❌ Wrong! No path specified
```

**Result:**
- Exporter failed to send data (wrong URL)
- Collector never received anything
- No error messages (silent failure)
- JSONL files stayed empty

## The Fix

**After the fix:**
```typescript
// Config parser now adds paths for HTTP:
if (protocol === "http" && !endpoint.endsWith("/v1/metrics")) {
  endpoint = endpoint.replace(/\/$/, "")  // Remove trailing slash
  endpoint = `${endpoint}/v1/metrics`     // Add OTLP path
}

// Now exporter sends to:
http://localhost:4318/v1/metrics  // ✅ Correct!
```

**File: `src/config.ts`**

**Changes:**
1. `parseMetricsConfig()` - Appends `/v1/metrics` for HTTP protocol
2. `parseTracesConfig()` - Appends `/v1/traces` for HTTP protocol

**Smart handling:**
- Only adds path if protocol is `http`
- Checks if path already exists (prevents double-adding)
- Removes trailing slash before appending
- gRPC URLs remain unchanged

## Why This Wasn't Obvious

1. **No error messages** - The exporter silently failed without errors
2. **Collector was running** - Everything looked fine on the collector side
3. **Plugin initialized** - Logs showed "Metrics initialized http://localhost:4318"
4. **Data was collected** - Plugin logs showed LOC events, permissions, etc.

The only clue was: **Collector logs showed NO incoming data**.

## How to Verify the Fix

### 1. Check Plugin Logs

**Before fix:**
```
[telemetry-plugin] Initializing metrics with config:
  Endpoint: http://localhost:4318  ← Missing path!
```

**After fix:**
```
[telemetry-plugin] Initializing metrics with config:
  Endpoint: http://localhost:4318/v1/metrics  ← Has path! ✓
```

### 2. Check Collector Logs

**After fix, you should see:**
```
otel-collector | ResourceMetrics #0
otel-collector | Resource SchemaURL:
otel-collector | ScopeMetrics #0
otel-collector | Metric #0
```

### 3. Check JSONL Files

**After making edits:**
```bash
tail -f /home/<username>/opencode/otel-data/metrics.jsonl
# Should show JSON lines with metrics data!
```

## OTLP HTTP Endpoints Reference

| Signal | HTTP Path | Full URL (default) |
|--------|-----------|-------------------|
| Metrics | `/v1/metrics` | `http://localhost:4318/v1/metrics` |
| Traces | `/v1/traces` | `http://localhost:4318/v1/traces` |
| Logs | `/v1/logs` | `http://localhost:4318/v1/logs` |

**gRPC:** No paths needed, just `http://localhost:4317`

## Testing Instructions

### Quick Test

```bash
# 1. Rebuild plugin
npm run build

# 2. Clear everything
./view-logs.sh clear
cd /home/<username>/opencode && > otel-data/metrics.jsonl && > otel-data/traces.jsonl

# 3. Run OpenCode
opencode

# 4. Check logs for paths
./view-logs.sh | grep "Endpoint:"
# Should show: /v1/metrics and /v1/traces

# 5. Make edits, then check files
tail -f /home/<username>/opencode/otel-data/metrics.jsonl
```

### Watch Collector Logs

```bash
docker-compose logs -f otel-collector
```

**You should see:**
- `ResourceMetrics` being received
- `ResourceSpans` being received
- Data being exported to files

## Environment Variables Still Work

The fix works with both defaults and environment variables:

```bash
# Base URL only (path added automatically for HTTP)
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"
export OTEL_EXPORTER_OTLP_PROTOCOL="http"

# Or full URL with paths (won't double-add)
export OTEL_EXPORTER_OTLP_METRICS_ENDPOINT="http://localhost:4318/v1/metrics"
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="http://localhost:4318/v1/traces"
```

## Key Takeaways

1. **HTTP ≠ gRPC** - Different protocols, different URL formats
2. **OTLP/HTTP requires paths** - Must include `/v1/metrics` or `/v1/traces`
3. **Silent failures** - No errors, just no data
4. **Port numbers matter**:
   - 4317 = gRPC (no paths)
   - 4318 = HTTP (needs paths)

## References

- [OTLP Specification](https://opentelemetry.io/docs/specs/otlp/)
- [OTLP HTTP](https://opentelemetry.io/docs/specs/otlp/#otlphttp)
- [OTLP gRPC](https://opentelemetry.io/docs/specs/otlp/#otlpgrpc)

## Success Criteria

After this fix, you should see:

- ✅ Plugin logs show full URLs with paths
- ✅ Collector logs show incoming data
- ✅ metrics.jsonl has JSON data
- ✅ traces.jsonl has JSON data
- ✅ No silent failures

The telemetry pipeline is now working end-to-end! 🎉
