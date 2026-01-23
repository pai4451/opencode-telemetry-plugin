# Getting Started with Trace-Metrics Correlation

Quick start guide to begin analyzing user behavior with trace-metrics correlation.

## Quick Start (5 minutes)

### 1. Verify Plugin is Built

```bash
cd /home/mtk26468/opencode-telemetry-plugin
npm run build
```

Expected output: `> tsc` (no errors)

### 2. Test Current Data

```bash
# Run the test script
./test-correlation.sh
```

This will verify:
- ✓ Traces can be parsed
- ✓ call_id correlation keys are present
- ✓ Session context (may need new data)

### 3. Run Full Demo

```bash
# Process all data and show correlation examples
./demo-correlation.sh
```

This will:
1. Parse traces → MongoDB `prompt` collection
2. Parse metrics → MongoDB `metrics` collection
3. Verify correlation keys match
4. Run example correlation query

### 4. Generate New Data with Session Context

The existing traces don't have session context yet. To get full correlation:

1. Use OpenCode with the rebuilt plugin
2. Make some edits (accept or reject them)
3. Re-run the demo: `./demo-correlation.sh`

Now you'll see session_id, user, and file_path populated in traces!

## What You Can Do Now

### View Data

```bash
# See trace analysis
python3 analyze_traces.py

# See sample records
python3 analyze_traces.py --show-records
```

### Run Correlation Queries

```bash
# Start MongoDB shell
mongosh opencode_telemetry

# Or traditional mongo CLI
mongo opencode_telemetry
```

Then try these queries:

**What prompts led to accepted edits?**
```javascript
db.metrics.aggregate([
  { $match: { accept: true } },
  { $lookup: { from: "prompt", localField: "call_id", foreignField: "call_id", as: "p" }},
  { $unwind: "$p" },
  { $project: { user_prompt: "$p.user_prompt", filepath: 1, ai_loc: 1, tokens: "$p.total_tokens" }},
  { $limit: 5 }
])
```

**User acceptance rates**
```javascript
db.metrics.aggregate([
  { $group: {
      _id: "$user",
      total: { $sum: 1 },
      accepted: { $sum: { $cond: ["$accept", 1, 0] } }
  }},
  { $project: {
      user: "$_id",
      total: 1,
      accepted: 1,
      rate: { $multiply: [{ $divide: ["$accepted", "$total"] }, 100] }
  }}
])
```

**Token usage by user**
```javascript
db.prompt.aggregate([
  { $group: {
      _id: "$user",
      total_tokens: { $sum: "$total_tokens" },
      prompts: { $sum: 1 }
  }},
  { $project: {
      user: "$_id",
      total_tokens: 1,
      prompts: 1,
      avg_tokens: { $divide: ["$total_tokens", "$prompts"] }
  }},
  { $sort: { total_tokens: -1 } }
])
```

## File Reference

| File | Purpose | Usage |
|------|---------|-------|
| `analyze_traces.py` | Parse traces | `python3 analyze_traces.py --to-mongo` |
| `analyze_metrics.py` | Parse metrics | `python3 analyze_metrics.py --to-mongo` |
| `test-correlation.sh` | Verify setup | `./test-correlation.sh` |
| `demo-correlation.sh` | Full demo | `./demo-correlation.sh` |
| `CORRELATION_GUIDE.md` | Full documentation | Read for in-depth info |
| `CORRELATION_QUICK_REFERENCE.md` | Query examples | Quick query lookup |
| `CORRELATION_IMPLEMENTATION_SUMMARY.md` | What was built | Technical details |

## Common Workflows

### Daily Analysis

```bash
# Process new data (run daily or after sessions)
python3 analyze_traces.py --to-mongo
python3 analyze_metrics.py --to-mongo

# Check summary
mongosh opencode_telemetry --eval "
  print('Prompts:', db.prompt.count());
  print('Metrics:', db.metrics.count())
"
```

### Weekly Reports

```javascript
// In MongoDB shell
// Acceptance rate this week
db.metrics.aggregate([
  { $match: {
      time: { $gte: "2026-01-17T00:00:00+00:00" }
  }},
  { $group: {
      _id: null,
      total: { $sum: 1 },
      accepted: { $sum: { $cond: ["$accept", 1, 0] } }
  }},
  { $project: {
      total: 1,
      accepted: 1,
      rate: { $multiply: [{ $divide: ["$accepted", "$total"] }, 100] }
  }}
])

// Token usage this week
db.prompt.aggregate([
  { $match: {
      time: { $gte: "2026-01-17T00:00:00+00:00" }
  }},
  { $group: {
      _id: null,
      total_tokens: { $sum: "$total_tokens" },
      prompts: { $sum: 1 }
  }}
])
```

### User-Specific Analysis

```javascript
// Replace "mtk26468" with actual username
var user = "mtk26468";

// User's acceptance rate
db.metrics.aggregate([
  { $match: { user: user } },
  { $group: {
      _id: null,
      total: { $sum: 1 },
      accepted: { $sum: { $cond: ["$accept", 1, 0] } }
  }},
  { $project: {
      rate: { $multiply: [{ $divide: ["$accepted", "$total"] }, 100] }
  }}
])

// User's top prompts
db.prompt.aggregate([
  { $match: { user: user } },
  { $group: {
      _id: { $substr: ["$user_prompt", 0, 50] },
      count: { $sum: 1 },
      avg_tokens: { $avg: "$total_tokens" }
  }},
  { $sort: { count: -1 } },
  { $limit: 5 }
])
```

## Troubleshooting

### "No records extracted"

**Cause**: No traces.jsonl file or empty file

**Solution**:
```bash
# Check if file exists
ls -lh /home/mtk26468/opencode/otel-data/traces.jsonl

# If empty, use OpenCode with telemetry enabled
# Make sure experimental.openTelemetry = true in config
```

### "session_id is null"

**Cause**: Traces collected before plugin enhancement

**Solution**:
```bash
# Rebuild plugin
npm run build

# Use OpenCode to generate new traces
# They will have session context

# Re-process
python3 analyze_traces.py --to-mongo
```

### "No matching records in join"

**Cause**: Metrics and traces from different sessions

**Solution**:
```bash
# Check both collections
mongosh opencode_telemetry --eval "
  db.metrics.findOne({}, {call_id: 1});
  db.prompt.findOne({}, {call_id: 1})
"

# If call_ids don't match, need to collect new data
# where both metrics and traces are captured together
```

### "MongoDB connection refused"

**Cause**: MongoDB not running

**Solution**:
```bash
# Start MongoDB
sudo systemctl start mongod

# Or if using Docker
docker-compose up -d
```

## Performance Optimization

### Create Indexes (First Time)

```javascript
// In MongoDB shell
db.metrics.createIndex({ call_id: 1 })
db.prompt.createIndex({ call_id: 1 })
db.metrics.createIndex({ user: 1, accept: 1 })
db.prompt.createIndex({ session_id: 1 })
db.metrics.createIndex({ time: 1 })
db.prompt.createIndex({ time: 1 })
```

This will make queries much faster!

### Archive Old Data (Monthly)

```javascript
// Delete data older than 90 days
var cutoffDate = new Date(Date.now() - 90*24*60*60*1000).toISOString()

db.metrics.deleteMany({ time: { $lt: cutoffDate } })
db.prompt.deleteMany({ time: { $lt: cutoffDate } })
```

## Next Steps

1. **Read the full guide**: `cat CORRELATION_GUIDE.md`
2. **Try query examples**: `cat CORRELATION_QUICK_REFERENCE.md`
3. **Review implementation**: `cat CORRELATION_IMPLEMENTATION_SUMMARY.md`
4. **Start collecting data**: Use OpenCode with telemetry enabled!

## Need Help?

- **Documentation**: All `.md` files in this directory
- **Test Setup**: `./test-correlation.sh`
- **Demo**: `./demo-correlation.sh`
- **Script Help**: `python3 analyze_traces.py --help`

## Key Takeaways

✅ **Correlation works via `call_id`** - exact 1:1 matching

✅ **Session context is optional** - nice to have but not required

✅ **MongoDB makes queries easy** - powerful aggregation framework

✅ **Start analyzing today** - run the demo script!

---

**You're all set!** Start with `./demo-correlation.sh` to see it in action.
