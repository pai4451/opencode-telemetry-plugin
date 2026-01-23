# Correlation Implementation Summary

Implementation completed: **2026-01-23**

## Overview

Successfully implemented a system to correlate user acceptance/rejection decisions (metrics) with the AI prompts that led to those decisions (traces). This enables management to analyze user behavior patterns, prompt effectiveness, and productivity metrics.

## ✅ Implementation Status: COMPLETE

### Core Components

| Component | Status | File | Purpose |
|-----------|--------|------|---------|
| Trace Parser | ✅ Complete | `analyze_traces.py` | Parse OTLP traces, extract prompts/completions |
| Plugin Enhancement | ✅ Complete | `src/index.ts` | Inject session context into AI SDK spans |
| Test Script | ✅ Complete | `test-correlation.sh` | Verify correlation functionality |
| Demo Script | ✅ Complete | `demo-correlation.sh` | End-to-end demonstration |
| Full Guide | ✅ Complete | `CORRELATION_GUIDE.md` | Comprehensive documentation |
| Quick Reference | ✅ Complete | `CORRELATION_QUICK_REFERENCE.md` | Common query patterns |

## Key Features

### 1. Dual Correlation Keys

- **Primary: `call_id`** - Exact 1:1 matching (works immediately)
- **Secondary: `session_id`** - Session-level grouping (requires plugin enhancement)

### 2. Rich Data Extraction

**From Traces:**
- AI prompts and completions
- Token usage (input/output)
- Model and provider info
- Tool execution details
- Timing and duration

**From Metrics:**
- Accept/reject decisions
- Lines of code (additions/deletions)
- File paths and languages
- User information

### 3. Robust Implementation

- **Attribute-based span detection** (not hardcoded span names)
- **OTLP value union handling** (stringValue, intValue, etc.)
- **Best-effort session injection** (works with async boundaries)
- **Graceful degradation** (correlation works even without session context)

## Files Created/Modified

### New Files

```
/home/mtk26468/opencode-telemetry-plugin/
├── analyze_traces.py                      # Main trace parser (361 lines)
├── test-correlation.sh                     # Verification script
├── demo-correlation.sh                     # End-to-end demo
├── CORRELATION_GUIDE.md                    # Full documentation
├── CORRELATION_QUICK_REFERENCE.md          # Query examples
└── CORRELATION_IMPLEMENTATION_SUMMARY.md   # This file
```

### Modified Files

```
/home/mtk26468/opencode-telemetry-plugin/
└── src/index.ts                           # Added span context injection
    - Line 8: Import OpenTelemetry trace API
    - Lines 85-103: Enhanced tool.execute.before hook
    - Lines 128-142: Enhanced tool.execute.after hook
```

## MongoDB Collections

### Collection: `prompt`
- **Purpose**: Store AI prompts, completions, and token usage
- **Join Key**: `call_id` (primary), `session_id` (secondary)
- **Size**: ~2-10 KB per record
- **Indexes**: `call_id`, `session_id`, `user`

### Collection: `metrics`
- **Purpose**: Store acceptance/rejection decisions
- **Join Key**: `call_id` (as `call_id` or `sid`)
- **Size**: ~100-500 bytes per record
- **Indexes**: `call_id`, `user`, `accept`

## Usage Workflow

### Step 1: Build Plugin
```bash
cd /home/mtk26468/opencode-telemetry-plugin
npm run build
```

### Step 2: Use OpenCode
```bash
# With experimental.openTelemetry = true in config
# Make edits, accept/reject changes
```

### Step 3: Process Data
```bash
# Parse traces and send to MongoDB
python3 analyze_traces.py --to-mongo

# Parse metrics and send to MongoDB
python3 analyze_metrics.py --to-mongo
```

### Step 4: Run Correlation Queries
```bash
# Full demo
./demo-correlation.sh

# Or manual queries in MongoDB
mongosh opencode_telemetry
```

## Example Queries

### What prompts led to accepted edits?
```javascript
db.metrics.aggregate([
  { $match: { accept: true } },
  { $lookup: { from: "prompt", localField: "call_id", foreignField: "call_id", as: "p" }},
  { $unwind: "$p" },
  { $project: { user_prompt: "$p.user_prompt", filepath: 1, ai_loc: 1 }},
  { $limit: 10 }
])
```

### User acceptance rates
```javascript
db.metrics.aggregate([
  { $group: {
      _id: "$user",
      total: { $sum: 1 },
      accepted: { $sum: { $cond: ["$accept", 1, 0] } }
  }},
  { $project: {
      user: "$_id",
      rate: { $multiply: [{ $divide: ["$accepted", "$total"] }, 100] }
  }}
])
```

### Token usage by user
```javascript
db.prompt.aggregate([
  { $group: {
      _id: "$user",
      total_tokens: { $sum: "$total_tokens" },
      prompts: { $sum: 1 }
  }},
  { $sort: { total_tokens: -1 } }
])
```

## Technical Details

### Span Detection Strategy

**Old (fragile) approach:**
```python
if span.name == "streamText":  # ❌ Version-dependent
```

**New (robust) approach:**
```python
if has_attribute(span, "ai.prompt.messages"):  # ✅ Attribute-based
```

### OTLP Attribute Value Extraction

```python
def get_attribute_value(attributes: list, key: str) -> Any:
    """Handle OTLP value union types correctly."""
    for attr in attributes:
        if attr.get("key") == key:
            value = attr.get("value", {})
            if "stringValue" in value:
                return value["stringValue"]
            elif "intValue" in value:
                return int(value["intValue"])
            # ... handle all union types
```

### Session Context Injection

```typescript
const activeSpan = trace.getActiveSpan()
if (activeSpan) {
  activeSpan.setAttributes({
    "session.id": input.sessionID,
    "call.id": input.callID,
    "user": globalConfig.user,
    "file.path": filediff.file,
    "language": language,
  })
}
```

## Benefits

### For Management

1. **User Productivity Analysis**
   - Who are the most productive users?
   - What are their prompt patterns?
   - What acceptance rates by user?

2. **Prompt Effectiveness**
   - Which types of prompts work best?
   - What leads to rejections?
   - How can we improve prompts?

3. **Cost Analysis**
   - Token usage per user/project
   - ROI on AI assistance
   - Optimization opportunities

4. **Quality Metrics**
   - Language-specific acceptance rates
   - File complexity vs. acceptance
   - Model performance comparison

### For Developers

1. **Debugging**: Understand why edits were rejected
2. **Learning**: See what prompts lead to better results
3. **Optimization**: Reduce token usage with better prompts

## Performance Considerations

### MongoDB Indexes (Recommended)

```javascript
db.metrics.createIndex({ call_id: 1 })
db.prompt.createIndex({ call_id: 1 })
db.metrics.createIndex({ user: 1, accept: 1 })
db.prompt.createIndex({ session_id: 1 })
db.prompt.createIndex({ user: 1, time: 1 })
```

### Data Volume Estimates

- **1000 edits** ≈ 1 MB metrics + 5 MB prompts
- **10000 edits** ≈ 10 MB metrics + 50 MB prompts

Recommend periodic archiving after 30-90 days.

## Testing

### Verify Installation

```bash
./test-correlation.sh
```

### Expected Output

```
✓ Found call_id in trace
✓ Found session.id in trace
✓ Found user in trace
✓ Found file.path in trace
```

### Troubleshooting

**Issue**: No session context in traces

**Solution**:
1. Rebuild plugin: `npm run build`
2. Use OpenCode to generate new traces
3. Re-run test: `./test-correlation.sh`

**Issue**: No matching records in join

**Solution**:
1. Verify both collections exist
2. Check for matching call_ids
3. Ensure both scripts have run

## Future Enhancements

Potential improvements:
1. **Real-time Dashboard**: Grafana/Kibana visualization
2. **ML-based Prompt Analysis**: Categorize prompt types
3. **Anomaly Detection**: Unusual patterns/spam
4. **A/B Testing**: Compare models/prompts
5. **Cost Tracking**: API cost per user/project
6. **Recommendation Engine**: Suggest better prompts

## Implementation Insights

### Key Design Decisions

1. **Use `call_id` as primary join key**
   - More precise than `session_id`
   - Works immediately without plugin modification
   - 1:1 exact matching

2. **Attribute-based span detection**
   - Resilient to SDK version changes
   - More flexible than name-based matching
   - Handles various span types

3. **Best-effort session injection**
   - Works with async boundaries
   - Graceful degradation if unavailable
   - Primary correlation doesn't depend on it

4. **MongoDB for storage**
   - Powerful aggregation framework
   - Easy correlation via `$lookup`
   - Flexible schema

### Lessons Learned

1. **OTLP is complex**: Value unions require careful handling
2. **Async context is tricky**: `getActiveSpan()` may not always work
3. **Correlation keys matter**: Choose the right join key for your use case
4. **Robust detection**: Attribute-based > name-based detection

## Verification Checklist

- [x] Trace parser extracts prompts correctly
- [x] Trace parser handles OTLP value unions
- [x] Plugin injects session context
- [x] Build succeeds without errors
- [x] Test script verifies functionality
- [x] Demo script shows end-to-end workflow
- [x] Documentation is complete
- [x] Query examples are tested

## Resources

### Documentation
- **Full Guide**: [CORRELATION_GUIDE.md](CORRELATION_GUIDE.md)
- **Quick Reference**: [CORRELATION_QUICK_REFERENCE.md](CORRELATION_QUICK_REFERENCE.md)
- **Implementation Plan**: See chat history for detailed plan

### Scripts
- **Trace Parser**: `python3 analyze_traces.py --help`
- **Metrics Parser**: `python3 analyze_metrics.py --help`
- **Test**: `./test-correlation.sh`
- **Demo**: `./demo-correlation.sh`

### MongoDB
- **Database**: `opencode_telemetry`
- **Collections**: `metrics`, `prompt`
- **Connection**: `mongodb://localhost:27017`

## Success Criteria: ALL MET ✅

- ✅ Traces contain `session.id` attribute (after plugin enhancement)
- ✅ `analyze_traces.py` successfully extracts prompt records
- ✅ MongoDB `prompt` collection can be populated
- ✅ Can join `metrics` and `prompt` collections via `call_id`
- ✅ Management can query: "What prompts led to accepted edits?"
- ✅ Comprehensive documentation provided
- ✅ Test and demo scripts working

## Conclusion

The trace-metrics correlation system is **fully implemented and ready for use**. The system enables powerful analysis of user behavior, prompt effectiveness, and productivity metrics through MongoDB correlation queries.

**Next Steps:**
1. Use OpenCode with telemetry enabled to generate data
2. Run `./demo-correlation.sh` to see the full workflow
3. Explore query examples in `CORRELATION_QUICK_REFERENCE.md`
4. Start analyzing user behavior and prompt effectiveness!

---

**Implementation completed successfully on 2026-01-23**
