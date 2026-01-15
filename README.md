# OpenCode Telemetry Plugin

A zero-configuration OpenTelemetry plugin for OpenCode that collects detailed metrics about AI-assisted code editing sessions.

## Features

- 📊 **Lines of Code (LOC) Tracking** - Track additions and deletions per edit
- 🛠️ **Tool Execution Metrics** - Monitor tool usage and performance
- 📁 **File & Language Attribution** - See which files and languages are modified
- ⚡ **Near Real-time Export** - Metrics exported every 5 seconds
- 🔄 **DELTA Temporality** - Clean data with no duplicates
- 📝 **File-based Logging** - Separate log file for debugging
- 🚀 **Zero Config** - Works out of the box with `experimental.openTelemetry: true`

## What Metrics Are Collected?

### 1. Lines of Code (LOC)

**Metrics:**
- `opencode.tool.loc.added` - Number of lines added by AI tools
- `opencode.tool.loc.deleted` - Number of lines deleted by AI tools

**Attributes:**
- `tool.name` - The tool that made the change (e.g., "edit", "write")
- `language` - Programming language detected from file extension
- `file.path` - Path to the modified file
- `session.id` - Unique session identifier

**Example:**
```
Tool: edit
Language: typescript
File: src/index.ts
Added: +15 lines
Deleted: -3 lines
```

### 2. Tool Execution Counts

**Metric:**
- `opencode.tool.executions` - Number of times each tool was executed

**Attributes:**
- `tool.name` - Tool name (edit, read, write, bash, etc.)
- `tool.status` - Execution status (success, error)
- `language` - Language of files being operated on
- `session.id` - Session identifier

**Example:**
```
Tool: edit, Status: success, Count: 25
Tool: read, Status: success, Count: 10
Tool: bash, Status: success, Count: 5
```

### 3. Tool Execution Duration

**Metric:**
- `opencode.tool.duration` - Histogram of tool execution times

**Attributes:**
- `tool.name` - Tool that was executed
- `tool.status` - Execution status
- `language` - Language context
- `session.id` - Session identifier

**Values:**
- `count` - Number of executions
- `sum` - Total duration (milliseconds)
- `min` - Fastest execution
- `max` - Slowest execution
- Histogram buckets for distribution analysis

### 4. Permission Requests (Future)

**Metric:**
- `opencode.permission.requests` - Permission ask/accept/reject stats

**Attributes:**
- `permission` - Type of permission requested
- `reply` - User response (accept, reject, always)
- `tool.name` - Tool requesting permission
- `session.id` - Session identifier

## Installation

### 1. Build the Plugin

```bash
cd /home/mtk26468/opencode-telemetry-plugin
npm install
npm run build
```

### 2. Link to OpenCode

Create a symlink in your OpenCode project:

```bash
cd /path/to/your/opencode/project
mkdir -p .opencode/plugin
ln -s /home/mtk26468/opencode-telemetry-plugin .opencode/plugin/opencode-telemetry
```

### 3. Configure OpenCode

Add to your OpenCode config (`~/.config/opencode/opencode.jsonc` or project's `.opencode/opencode.jsonc`):

```jsonc
{
  "plugin": [
    "file:///path/to/.opencode/plugin/opencode-telemetry"
  ],
  "experimental": {
    "openTelemetry": true
  }
}
```

**That's it!** The plugin will automatically:
- Initialize when OpenCode starts
- Export metrics to `http://localhost:4317` (OTEL collector)
- Log to `~/.local/share/opencode/telemetry-plugin.log`

## OTEL Collector Setup

### Docker Compose (Recommended)

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  otel-collector:
    image: otel/opentelemetry-collector:latest
    container_name: opencode-otel-collector
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./otel-collector-config.yaml:/etc/otel-collector-config.yaml
      - ./otel-data:/otel-data
    ports:
      - "4317:4317"  # OTLP gRPC receiver
      - "4318:4318"  # OTLP HTTP receiver
    restart: unless-stopped
```

### OTEL Collector Config

Create `otel-collector-config.yaml`:

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

exporters:
  debug:
    verbosity: detailed

  # Metrics exporter - writes to metrics.jsonl
  file/metrics:
    path: /otel-data/metrics.jsonl
    rotation:
      max_megabytes: 10
      max_backups: 3

  # Traces exporter (for future use)
  file/traces:
    path: /otel-data/traces.jsonl
    rotation:
      max_megabytes: 10
      max_backups: 3

service:
  pipelines:
    metrics:
      receivers: [otlp]
      exporters: [debug, file/metrics]

    traces:
      receivers: [otlp]
      exporters: [debug, file/traces]
```

### Start the Collector

```bash
docker-compose up -d
```

## Usage

### Start OpenCode

Just run OpenCode normally:

```bash
opencode
```

The plugin will:
1. Load automatically when OpenCode starts
2. Begin tracking metrics immediately
3. Export data every 5 seconds to OTEL collector
4. Write logs to `~/.local/share/opencode/telemetry-plugin.log`

### View Logs

```bash
./view-logs.sh           # Show last 50 lines
./view-logs.sh follow    # Follow logs in real-time
./view-logs.sh loc       # Show only LOC recordings
./view-logs.sh summary   # Show summary statistics
./view-logs.sh clear     # Clear log file
```

**Log Location:** `~/.local/share/opencode/telemetry-plugin.log`

### View Metrics

```bash
./view-metrics.sh        # Parse and display metrics.jsonl
```

**Metrics Location:** `./otel-data/metrics.jsonl` (relative to OTEL collector)

### Raw Data

View raw JSONL data:

```bash
# Follow metrics in real-time
tail -f /path/to/otel-data/metrics.jsonl

# With jq for pretty printing (install jq first)
tail -f /path/to/otel-data/metrics.jsonl | jq '.'

# Count entries
wc -l /path/to/otel-data/metrics.jsonl
```

## Data Format

### JSONL Export Format

Each line in `metrics.jsonl` is a JSON object in OpenTelemetry format:

```json
{
  "resourceMetrics": [{
    "resource": {
      "attributes": [
        {"key": "service.name", "value": {"stringValue": "opencode"}},
        {"key": "service.version", "value": {"stringValue": "plugin-1.0.0"}},
        {"key": "opencode.plugin", "value": {"stringValue": "telemetry"}}
      ]
    },
    "scopeMetrics": [{
      "scope": {"name": "opencode", "version": "1.0.0"},
      "metrics": [{
        "name": "opencode.tool.loc.added",
        "unit": "lines",
        "sum": {
          "dataPoints": [{
            "attributes": [
              {"key": "tool.name", "value": {"stringValue": "edit"}},
              {"key": "language", "value": {"stringValue": "typescript"}},
              {"key": "file.path", "value": {"stringValue": "/path/to/file.ts"}},
              {"key": "session.id", "value": {"stringValue": "ses_abc123"}}
            ],
            "timeUnixNano": "1705305600000000000",
            "asDouble": 15
          }],
          "aggregationTemporality": 1,
          "isMonotonic": true
        }
      }]
    }]
  }]
}
```

### DELTA Temporality

The plugin uses **DELTA temporality**, meaning:
- Each export shows **changes since last export**
- No duplicate cumulative data
- Clean, easy to sum

**Example:**
```
Export 1: +15 lines added (actual change)
Export 2: +0 lines (no activity)
Export 3: +10 lines added (new change)

Total: 15 + 0 + 10 = 25 lines added
```

## Architecture

### Plugin Flow

```
OpenCode → Plugin Hooks → Metrics Collection → OTEL SDK → OTEL Collector → JSONL Files
              ↓
    tool.execute.before
    tool.execute.after
    event (permissions)
              ↓
    Correlation Maps (link events)
              ↓
    Record Metrics (LOC, duration, counts)
              ↓
    Export every 5 seconds (DELTA mode)
```

### Components

**`src/index.ts`**
- Plugin entry point
- Hooks into OpenCode events
- Initializes metrics when `openTelemetry: true`

**`src/metrics.ts`**
- OpenTelemetry SDK setup
- Metric instruments (counters, histograms)
- DELTA temporality configuration
- Export to OTLP endpoint

**`src/correlation.ts`**
- Links tool executions with metadata
- Tracks call IDs and contexts
- Enables accurate attribution

**`src/language-map.ts`**
- Maps file extensions to languages
- Supports 80+ programming languages

**`src/logger.ts`**
- File-based logging system
- Writes to `~/.local/share/opencode/telemetry-plugin.log`
- Automatic rotation at 10MB

**`src/types.ts`**
- TypeScript type definitions

## Configuration

### Default Settings

The plugin uses sensible defaults:

```typescript
{
  enabled: true,
  endpoint: "http://localhost:4317",
  protocol: "grpc",
  exportIntervalMillis: 5000  // 5 seconds
}
```

### Customization

To customize, modify `src/index.ts`:

```typescript
const metricsConfig: MetricsConfig = {
  enabled: true,
  endpoint: "http://your-otel-collector:4317",  // Custom endpoint
  protocol: "grpc",  // or "http"
  exportIntervalMillis: 10000,  // 10 seconds instead of 5
}
```

Then rebuild:

```bash
npm run build
```

## Troubleshooting

### Plugin Not Loading?

**Check:**
1. Plugin is linked correctly in `.opencode/plugin/`
2. Config has `"experimental": {"openTelemetry": true}`
3. OpenCode was restarted after config change

**Verify:**
```bash
# Should see plugin load message on startup
grep "Plugin loaded" ~/.local/share/opencode/telemetry-plugin.log
```

### No Metrics in JSONL?

**Check:**
1. OTEL collector is running: `docker ps | grep otel`
2. Plugin initialized: `grep "Metrics initialized" ~/.local/share/opencode/telemetry-plugin.log`
3. You made edits in OpenCode
4. Wait 5 seconds for export

**Verify:**
```bash
# Check OTEL collector logs
docker logs opencode-otel-collector --tail 50

# Check metrics file
ls -lh /path/to/otel-data/metrics.jsonl
```

### Metrics Delayed?

**Expected behavior:**
- Plugin logs LOC **immediately**
- OTEL exports every **5 seconds**
- Metrics appear in JSONL within **5-10 seconds** of edit

If longer delay, check:
- OTEL collector is running
- No network issues with `localhost:4317`

### Duplicate Data?

**Should NOT happen** with DELTA temporality. If you see duplicate cumulative values:
- Verify `temporalityPreference: AggregationTemporality.DELTA` in `src/metrics.ts`
- Rebuild plugin: `npm run build`
- Restart OTEL collector

## Performance

### Resource Usage

- **CPU**: Negligible (<1% during exports)
- **Memory**: ~10-20MB for OTEL SDK
- **Disk**: ~1KB per export, rotates at 10MB
- **Network**: Minimal (localhost OTLP)

### Export Frequency

With **5-second intervals**:
- 12 exports per minute
- ~720 exports per hour
- ~600KB file per hour of active coding

### File Rotation

Automatic rotation configured:
- Maximum file size: 10MB
- Backups kept: 3
- Old files: `metrics-YYYY-MM-DD-HH-MM-SS.jsonl`

## Language Support

The plugin automatically detects languages from file extensions:

**Supported languages (80+):**
- JavaScript/TypeScript (.js, .jsx, .ts, .tsx)
- Python (.py)
- Java (.java)
- C/C++ (.c, .cpp, .h, .hpp)
- Go (.go)
- Rust (.rs)
- Ruby (.rb)
- PHP (.php)
- Swift (.swift)
- Kotlin (.kt)
- And many more...

See `src/language-map.ts` for full list.

## Use Cases

### Development Analytics

Track your AI-assisted development:
- How many lines of code generated per session?
- Which languages are you working with most?
- How long do different tools take?
- What's your accept/reject rate?

### Team Metrics

Aggregate data across team members:
- Total LOC generated by AI
- Most modified files
- Tool usage patterns
- Language distribution

### Research & Analysis

Export data for research:
- AI coding assistance effectiveness
- Developer productivity metrics
- Tool performance analysis
- Language-specific patterns

## Future Enhancements

Potential additions:
- [ ] Configurable export interval via config
- [ ] Flush metrics on OpenCode shutdown
- [ ] Trace support for tool execution spans
- [ ] Prometheus direct export
- [ ] Grafana dashboard templates
- [ ] Cost tracking (API tokens)
- [ ] Session replay metadata

## Contributing

This plugin was developed for OpenCode's plugin system. To extend:

1. Clone/fork the repository
2. Make changes in `src/`
3. Build: `npm run build`
4. Test with OpenCode
5. Submit improvements!

## License

MIT License - See your project's LICENSE file

## Credits

Built with:
- [@opentelemetry/sdk-metrics](https://www.npmjs.com/package/@opentelemetry/sdk-metrics)
- [@opentelemetry/exporter-metrics-otlp-grpc](https://www.npmjs.com/package/@opentelemetry/exporter-metrics-otlp-grpc)
- [@opencode-ai/plugin](https://www.npmjs.com/package/@opencode-ai/plugin)

---

**Happy Coding with OpenCode! 🚀**

For questions or issues, check the plugin logs at `~/.local/share/opencode/telemetry-plugin.log`
