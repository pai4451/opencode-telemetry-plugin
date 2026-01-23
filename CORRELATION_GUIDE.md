# Trace-Metrics Correlation Guide

This guide explains how to correlate user acceptance/rejection decisions (metrics) with the AI prompts that led to those decisions (traces).

## Overview

The correlation system enables management to analyze user behavior:
- **When users accept edits**, what prompts/tasks were they working on?
- **When users reject edits**, what went wrong with the AI's understanding?
- **What types of prompts** lead to the highest acceptance rates?
- **Which users** are most productive, and what are they asking for?

## Architecture

### Data Flow

```
OpenCode Session
    ↓
Plugin captures events
    ↓
┌─────────────────┬─────────────────┐
│   Metrics       │    Traces       │
│ (metrics.jsonl) │ (traces.jsonl)  │
│                 │                 │
│ - Accept/Reject │ - AI Prompts    │
│ - Lines of Code │ - Completions   │
│ - call_id ←──────────→ call_id    │
│ - session_id    │ - session_id    │
│ - user          │ - token usage   │
│ - file_path     │ - model info    │
└─────────────────┴─────────────────┘
         ↓                 ↓
    analyze_metrics.py  analyze_traces.py
         ↓                 ↓
    ┌─────────────────────────┐
    │       MongoDB           │
    │                         │
    │  Collection: metrics    │
    │  Collection: prompt     │
    │                         │
    │  Join on: call_id       │
    └─────────────────────────┘
```

### Correlation Keys

The system supports two correlation methods:

1. **Primary: `call_id` (Recommended)**
   - Provides exact 1:1 matching between metrics and prompts
   - More precise than session-based correlation
   - Available immediately in existing traces
   - Format: `toolu_01DnUCdLswyoYKwsN9rZcFEA`

2. **Secondary: `session_id`**
   - Groups multiple prompts/metrics by user session
   - Enables session-level behavior analysis
   - Requires plugin enhancement (implemented)
   - Format: `ses_4169b74ceffeqZ3ewBvdyholgE`

## Implementation Status

### ✅ Completed

1. **Python Script**: `analyze_traces.py`
   - Parses OTLP trace format
   - Robust span detection (attribute-based, not name-based)
   - Extracts prompts, completions, token usage
   - Correlates spans within traces via `traceId`
   - Exports to MongoDB `prompt` collection

2. **Plugin Enhancement**: `src/index.ts`
   - Injects `session.id` into active spans
   - Adds `call.id`, `user`, `file.path`, `language`
   - Best-effort span injection (works with AI SDK async context)

3. **Test Script**: `test-correlation.sh`
   - Verifies trace parsing
   - Checks for correlation keys
   - Validates session context injection

### 📋 MongoDB Collections

#### Collection: `metrics`
```javascript
{
  "accept": true,              // User accepted the edit
  "ai_loc": 17,                // Lines of code in AI's edit
  "call_id": "toolu_01GLLHem3GLYhVwyVan23pNW",  // ← JOIN KEY
  "sid": "ses_4169b74ceffeqZ3ewBvdyholgE",
  "user": "mtk26468",
  "filepath": "/path/to/file.cpp",
  "language": "cpp",
  "time": "2026-01-23T05:48:52+00:00"
}
```

#### Collection: `prompt`
```javascript
{
  "call_id": "toolu_01GLLHem3GLYhVwyVan23pNW",  // ← JOIN KEY
  "session_id": "ses_4169b74ceffeqZ3ewBvdyholgE",
  "trace_id": "6e1b6c3eae9a11395c5ecdc72bedc82e",

  // Prompt data
  "user_prompt": "Please refactor this merge sort to remove templates",
  "prompt_messages": [...],    // Full conversation history
  "ai_response": "I'll refactor the code...",

  // Context
  "user": "mtk26468",
  "file_path": "/path/to/file.cpp",
  "language": "cpp",

  // Model info
  "model": "claude-sonnet-4-5-20250929",
  "provider": "anthropic",
  "temperature": 0.5,
  "max_tokens": 4096,

  // Token usage
  "prompt_tokens": 1234,
  "completion_tokens": 567,
  "total_tokens": 1801,

  // Tool info
  "tool_name": "edit",
  "tool_args": "{\"filePath\":\"/path/to/file.cpp\"}",

  // Timing
  "time": "2026-01-23T05:48:39+00:00",
  "duration_ms": 1380.5
}
```

## Usage

### Step 1: Collect Data

Use OpenCode with the plugin enabled to generate telemetry:

```bash
# In OpenCode, with experimental.openTelemetry = true
# Make some edits, accept/reject changes
```

Data will be written to:
- `/home/mtk26468/opencode/otel-data/metrics.jsonl`
- `/home/mtk26468/opencode/otel-data/traces.jsonl`

### Step 2: Parse Traces

```bash
# View summary
python3 analyze_traces.py

# See sample records
python3 analyze_traces.py --show-records

# Send to MongoDB
python3 analyze_traces.py --to-mongo
```

### Step 3: Parse Metrics

```bash
# If not already done
python3 analyze_metrics.py --to-mongo
```

### Step 4: Verify Correlation

```bash
# Run test script
./test-correlation.sh
```

### Step 5: Query Correlated Data

#### Example 1: Find Prompts for Accepted Edits

```javascript
// MongoDB shell
db.metrics.aggregate([
  { $match: { accept: true } },
  {
    $lookup: {
      from: "prompt",
      localField: "call_id",
      foreignField: "call_id",
      as: "prompt_data"
    }
  },
  { $unwind: "$prompt_data" },
  {
    $project: {
      user: 1,
      filepath: 1,
      ai_loc: 1,
      user_prompt: "$prompt_data.user_prompt",
      model: "$prompt_data.model",
      tokens: "$prompt_data.total_tokens"
    }
  },
  { $limit: 10 }
])
```

#### Example 2: Analyze Rejection Patterns

```javascript
// Find prompts that led to rejections
db.metrics.aggregate([
  { $match: { accept: false } },
  {
    $lookup: {
      from: "prompt",
      localField: "call_id",
      foreignField: "call_id",
      as: "prompt_data"
    }
  },
  { $unwind: "$prompt_data" },
  {
    $group: {
      _id: "$prompt_data.user_prompt",
      rejection_count: { $sum: 1 },
      avg_ai_loc: { $avg: "$ai_loc" },
      languages: { $addToSet: "$language" }
    }
  },
  { $sort: { rejection_count: -1 } },
  { $limit: 5 }
])
```

#### Example 3: User Productivity Analysis

```javascript
// Group by user and analyze their prompt patterns
db.metrics.aggregate([
  {
    $lookup: {
      from: "prompt",
      localField: "call_id",
      foreignField: "call_id",
      as: "prompt_data"
    }
  },
  { $unwind: "$prompt_data" },
  {
    $group: {
      _id: "$user",
      total_edits: { $sum: 1 },
      accepted_edits: {
        $sum: { $cond: ["$accept", 1, 0] }
      },
      total_loc: { $sum: "$ai_loc" },
      total_tokens: { $sum: "$prompt_data.total_tokens" },
      avg_prompt_length: { $avg: { $strLenCP: "$prompt_data.user_prompt" } }
    }
  },
  {
    $project: {
      user: "$_id",
      total_edits: 1,
      accepted_edits: 1,
      acceptance_rate: {
        $multiply: [
          { $divide: ["$accepted_edits", "$total_edits"] },
          100
        ]
      },
      total_loc: 1,
      total_tokens: 1,
      avg_prompt_length: { $round: ["$avg_prompt_length", 0] }
    }
  },
  { $sort: { acceptance_rate: -1 } }
])
```

#### Example 4: Most Effective Prompts

```javascript
// Find prompts with highest acceptance rates
db.metrics.aggregate([
  {
    $lookup: {
      from: "prompt",
      localField: "call_id",
      foreignField: "call_id",
      as: "prompt_data"
    }
  },
  { $unwind: "$prompt_data" },
  {
    $group: {
      _id: {
        $substr: ["$prompt_data.user_prompt", 0, 50]  // First 50 chars
      },
      total: { $sum: 1 },
      accepted: { $sum: { $cond: ["$accept", 1, 0] } },
      avg_tokens: { $avg: "$prompt_data.total_tokens" }
    }
  },
  {
    $match: { total: { $gte: 3 } }  // At least 3 occurrences
  },
  {
    $project: {
      prompt_prefix: "$_id",
      total: 1,
      accepted: 1,
      acceptance_rate: {
        $multiply: [{ $divide: ["$accepted", "$total"] }, 100]
      },
      avg_tokens: { $round: ["$avg_tokens", 0] }
    }
  },
  { $sort: { acceptance_rate: -1, total: -1 } },
  { $limit: 10 }
])
```

#### Example 5: Session-Level Analysis

```javascript
// Analyze entire user sessions
db.prompt.aggregate([
  { $match: { session_id: { $ne: null } } },
  {
    $group: {
      _id: "$session_id",
      user: { $first: "$user" },
      total_prompts: { $sum: 1 },
      total_tokens: { $sum: "$total_tokens" },
      unique_files: { $addToSet: "$file_path" },
      languages: { $addToSet: "$language" },
      start_time: { $min: "$time" },
      end_time: { $max: "$time" }
    }
  },
  {
    $project: {
      session_id: "$_id",
      user: 1,
      total_prompts: 1,
      total_tokens: 1,
      unique_files_count: { $size: "$unique_files" },
      languages: 1,
      duration_minutes: {
        $divide: [
          { $subtract: [
            { $dateFromString: { dateString: "$end_time" } },
            { $dateFromString: { dateString: "$start_time" } }
          ]},
          60000  // Convert ms to minutes
        ]
      }
    }
  },
  { $sort: { total_prompts: -1 } },
  { $limit: 10 }
])
```

## Troubleshooting

### Issue: No `session_id` in Traces

**Symptom**: `session_id`, `user`, `file_path` are `null` in prompt records.

**Solution**: This is expected for traces collected before the plugin enhancement. The correlation still works via `call_id`. To get session context:
1. Ensure plugin is rebuilt: `npm run build`
2. Use OpenCode to make new edits
3. Re-run: `python3 analyze_traces.py`

### Issue: No Matching Records in Join

**Symptom**: Join query returns empty results.

**Solution**:
1. Verify both collections exist:
   ```javascript
   db.metrics.count()
   db.prompt.count()
   ```

2. Check for matching `call_id` values:
   ```javascript
   db.metrics.findOne({}, {call_id: 1})
   db.prompt.findOne({}, {call_id: 1})
   ```

3. Ensure both scripts have been run:
   ```bash
   python3 analyze_metrics.py --to-mongo
   python3 analyze_traces.py --to-mongo
   ```

### Issue: `getActiveSpan()` Returns `null`

**Symptom**: Plugin logs show "No active span found".

**Solution**: This can happen if the AI SDK span context is not propagated correctly. The system still works via `call_id` join. The session context is a convenience feature, not required for correlation.

## Performance Considerations

### MongoDB Indexes

For better query performance, create indexes:

```javascript
// Index on join keys
db.metrics.createIndex({ call_id: 1 })
db.prompt.createIndex({ call_id: 1 })

// Index on session_id for session analysis
db.metrics.createIndex({ sid: 1 })
db.prompt.createIndex({ session_id: 1 })

// Index on accept for filtering
db.metrics.createIndex({ accept: 1 })

// Compound index for user analysis
db.metrics.createIndex({ user: 1, accept: 1 })
db.prompt.createIndex({ user: 1, time: 1 })
```

### Data Volume

- **Metrics**: ~1 record per accepted/rejected edit (~100-500 bytes)
- **Prompts**: ~1 record per tool call (~2-10 KB with full messages)
- **Estimated**: 1000 edits ≈ 1MB metrics + 5MB prompts

For large datasets, consider:
- Periodic archiving of old data
- Aggregating historical metrics
- Time-based partitioning

## Management Insights

### Key Metrics to Track

1. **Acceptance Rate by Prompt Type**
   - Which types of requests have highest acceptance?
   - Are refactoring requests more likely to be accepted than new features?

2. **Token Usage Efficiency**
   - Do longer prompts lead to better acceptance?
   - What's the ROI on token usage?

3. **User Productivity**
   - Which users are most productive?
   - What are their prompt patterns?

4. **Language-Specific Patterns**
   - Do certain languages have higher/lower acceptance rates?
   - Are some languages consuming more tokens?

5. **Session Characteristics**
   - How long are typical coding sessions?
   - How many prompts per session?
   - What's the context-switching pattern?

## Future Enhancements

Potential improvements:
1. **Real-time Dashboard**: Grafana/Kibana visualization
2. **Prompt Categorization**: ML-based classification of prompt types
3. **Anomaly Detection**: Detect unusual patterns (spam, errors)
4. **A/B Testing**: Compare different models/prompts
5. **Cost Analysis**: Track API costs per user/project

## References

- **Plan Document**: See full implementation plan in chat history
- **Metrics Analysis**: `analyze_metrics.py`
- **Trace Analysis**: `analyze_traces.py`
- **Plugin Code**: `src/index.ts`
- **Test Script**: `test-correlation.sh`
