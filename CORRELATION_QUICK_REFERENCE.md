# Correlation Quick Reference

Fast reference for common trace-metrics correlation queries.

## Setup

```bash
# Process data and send to MongoDB
python3 analyze_traces.py --to-mongo
python3 analyze_metrics.py --to-mongo

# Or run full demo
./demo-correlation.sh
```

## Quick Queries

### 1. What prompts led to accepted edits?

```javascript
db.metrics.aggregate([
  { $match: { accept: true } },
  { $lookup: {
      from: "prompt",
      localField: "call_id",
      foreignField: "call_id",
      as: "p"
  }},
  { $unwind: "$p" },
  { $project: {
      user_prompt: "$p.user_prompt",
      filepath: 1,
      ai_loc: 1,
      tokens: "$p.total_tokens"
  }},
  { $limit: 10 }
])
```

### 2. What prompts led to rejections?

```javascript
db.metrics.aggregate([
  { $match: { accept: false } },
  { $lookup: {
      from: "prompt",
      localField: "call_id",
      foreignField: "call_id",
      as: "p"
  }},
  { $unwind: "$p" },
  { $group: {
      _id: "$p.user_prompt",
      count: { $sum: 1 }
  }},
  { $sort: { count: -1 } },
  { $limit: 5 }
])
```

### 3. Acceptance rate by user

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
  }},
  { $sort: { rate: -1 } }
])
```

### 4. Token usage by user

```javascript
db.prompt.aggregate([
  { $group: {
      _id: "$user",
      total_tokens: { $sum: "$total_tokens" },
      prompt_count: { $sum: 1 }
  }},
  { $project: {
      user: "$_id",
      total_tokens: 1,
      prompt_count: 1,
      avg_tokens: { $round: [{ $divide: ["$total_tokens", "$prompt_count"] }, 0] }
  }},
  { $sort: { total_tokens: -1 } }
])
```

### 5. Most productive sessions

```javascript
db.prompt.aggregate([
  { $match: { session_id: { $ne: null } } },
  { $group: {
      _id: "$session_id",
      user: { $first: "$user" },
      prompts: { $sum: 1 },
      tokens: { $sum: "$total_tokens" },
      files: { $addToSet: "$file_path" }
  }},
  { $project: {
      session: "$_id",
      user: 1,
      prompts: 1,
      tokens: 1,
      unique_files: { $size: "$files" }
  }},
  { $sort: { prompts: -1 } },
  { $limit: 10 }
])
```

### 6. Language breakdown

```javascript
db.metrics.aggregate([
  { $group: {
      _id: "$language",
      total: { $sum: 1 },
      accepted: { $sum: { $cond: ["$accept", 1, 0] } },
      total_loc: { $sum: "$ai_loc" }
  }},
  { $project: {
      language: "$_id",
      total: 1,
      accepted: 1,
      rate: { $multiply: [{ $divide: ["$accepted", "$total"] }, 100] },
      total_loc: 1
  }},
  { $sort: { total: -1 } }
])
```

### 7. Most expensive prompts (by tokens)

```javascript
db.prompt.aggregate([
  { $sort: { total_tokens: -1 } },
  { $project: {
      _id: 0,
      user_prompt: { $substr: ["$user_prompt", 0, 60] },
      model: 1,
      total_tokens: 1,
      user: 1,
      time: 1
  }},
  { $limit: 10 }
])
```

### 8. Files with most edits

```javascript
db.metrics.aggregate([
  { $group: {
      _id: "$filepath",
      edits: { $sum: 1 },
      accepted: { $sum: { $cond: ["$accept", 1, 0] } },
      total_loc: { $sum: "$ai_loc" }
  }},
  { $project: {
      file: "$_id",
      edits: 1,
      accepted: 1,
      rate: { $multiply: [{ $divide: ["$accepted", "$edits"] }, 100] },
      total_loc: 1
  }},
  { $sort: { edits: -1 } },
  { $limit: 10 }
])
```

### 9. Time-based analysis (daily activity)

```javascript
db.metrics.aggregate([
  { $project: {
      date: { $dateToString: { format: "%Y-%m-%d", date: { $dateFromString: { dateString: "$time" } } } },
      accept: 1,
      ai_loc: 1
  }},
  { $group: {
      _id: "$date",
      total_edits: { $sum: 1 },
      accepted_edits: { $sum: { $cond: ["$accept", 1, 0] } },
      total_loc: { $sum: "$ai_loc" }
  }},
  { $sort: { _id: -1 } },
  { $limit: 7 }
])
```

### 10. Correlation summary (full picture)

```javascript
db.metrics.aggregate([
  { $lookup: {
      from: "prompt",
      localField: "call_id",
      foreignField: "call_id",
      as: "p"
  }},
  { $unwind: "$p" },
  { $facet: {
      "acceptance_stats": [
        { $group: {
            _id: null,
            total: { $sum: 1 },
            accepted: { $sum: { $cond: ["$accept", 1, 0] } }
        }},
        { $project: {
            _id: 0,
            total: 1,
            accepted: 1,
            rejected: { $subtract: ["$total", "$accepted"] },
            acceptance_rate: { $multiply: [{ $divide: ["$accepted", "$total"] }, 100] }
        }}
      ],
      "token_stats": [
        { $group: {
            _id: null,
            total_tokens: { $sum: "$p.total_tokens" },
            avg_tokens: { $avg: "$p.total_tokens" }
        }},
        { $project: {
            _id: 0,
            total_tokens: 1,
            avg_tokens: { $round: ["$avg_tokens", 0] }
        }}
      ],
      "top_users": [
        { $group: {
            _id: "$user",
            edits: { $sum: 1 }
        }},
        { $sort: { edits: -1 } },
        { $limit: 5 }
      ],
      "top_languages": [
        { $group: {
            _id: "$language",
            count: { $sum: 1 }
        }},
        { $sort: { count: -1 } },
        { $limit: 5 }
      ]
  }}
])
```

## Useful Filters

### Filter by date range
```javascript
{
  time: {
    $gte: "2026-01-20T00:00:00+00:00",
    $lt: "2026-01-24T00:00:00+00:00"
  }
}
```

### Filter by user
```javascript
{ user: "mtk26468" }
```

### Filter by language
```javascript
{ language: "cpp" }
```

### Filter by model
```javascript
{ model: "claude-sonnet-4-5-20250929" }
```

### Filter by session
```javascript
{ session_id: "ses_4169b74ceffeqZ3ewBvdyholgE" }
```

## Export Results

### To JSON file
```bash
mongosh opencode_telemetry --eval 'db.metrics.find({accept: true})' > accepted_edits.json
```

### To CSV (using mongoexport)
```bash
mongoexport --db=opencode_telemetry --collection=metrics --type=csv \
  --fields=call_id,accept,ai_loc,user,filepath,language,time \
  --out=metrics.csv
```

## Performance Tips

### Create indexes
```javascript
db.metrics.createIndex({ call_id: 1 })
db.prompt.createIndex({ call_id: 1 })
db.metrics.createIndex({ user: 1, accept: 1 })
db.prompt.createIndex({ session_id: 1 })
```

### Use explain for slow queries
```javascript
db.metrics.aggregate([...]).explain("executionStats")
```

### Limit large result sets
```javascript
{ $limit: 100 }
```

## Troubleshooting

### No results from join query?
```javascript
// Check both collections have data
db.metrics.count()
db.prompt.count()

// Check for matching call_ids
db.metrics.findOne({}, {call_id: 1})
db.prompt.findOne({}, {call_id: 1})
```

### Session context missing?
```javascript
// Check if session_id is populated
db.prompt.count({ session_id: { $ne: null } })

// If zero, plugin needs to be rebuilt and OpenCode reused
```

### Old data cleanup
```javascript
// Delete data older than 30 days
db.metrics.deleteMany({
  time: { $lt: new Date(Date.now() - 30*24*60*60*1000).toISOString() }
})
db.prompt.deleteMany({
  time: { $lt: new Date(Date.now() - 30*24*60*60*1000).toISOString() }
})
```

## See Also

- **Full Guide**: CORRELATION_GUIDE.md
- **Demo Script**: ./demo-correlation.sh
- **Test Script**: ./test-correlation.sh
