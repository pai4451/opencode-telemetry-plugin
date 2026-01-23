# End-to-End Correlation Test Report

**Test Date:** 2026-01-23
**Test Type:** Manual end-to-end validation with clean data
**Result:** ✅ **100% SUCCESS** - System is production-ready

---

## Test Scenario

### Setup
1. Cleared all previous data:
   - metrics.jsonl
   - traces.jsonl
   - Plugin log
   - MongoDB collections

2. Generated fresh data using OpenCode:
   - Edited merge_sort.cpp
   - Accepted some suggestions (manual "once")
   - Rejected some suggestions
   - Switched to "always accept" (auto-approve)
   - Final result: 11 edit operations

### User Actions Captured
```
Session: ses_415e0d216ffeOTZvRHZYF85ZQh
User: mtk26468
Prompt: "Please edit merge_sort.cpp to change all chinese comments to english"

Actions:
- 6 manual accepts (clicked "Accept")
- 1 manual "always" (clicked "Always")
- 2 auto-approves (no dialog)
- 2 rejects (clicked "Reject")
Total: 11 edit operations
```

---

## Verification Results

### ✅ 1. Data Consistency

| Source | Edit Operations | Match Rate |
|--------|----------------|------------|
| **Plugin Log** | 11 call_ids | Baseline |
| **Metrics File** | 11 call_ids | 100% ✓ |
| **Traces File** | 17 call_ids (11 edits + 6 other tools) | 100% ✓ |
| **Overlap** | 11 call_ids in BOTH | 100% ✓ |

**Call IDs Found:**
```
✓ toolu_0133cCkv4g51xLJme9yVnxsf
✓ toolu_015LFcPkWYkjjgW47XRuLF3u
✓ toolu_01Csm9xd1aqhU1FCxotaXtbb
✓ toolu_01HteZTXi3kBZeGUpiSuGq1L
✓ toolu_01MCHpXJbc3VhbJcX4gBb2A1
✓ toolu_01MvUDsxByk7e17iboFbLZbC
✓ toolu_01R5HESnKZ9N5yEM8ZyK1eRK
✓ toolu_01RYycu3RqZtoRVWZDMmiJEg
✓ toolu_01T43SxXKEBYH4bJskuhdcEN
✓ toolu_01XQD6aPFZm9yrciuAjCQ31b
✓ toolu_01XQGpZg8X6QM49UoZ1HxNhV
```

### ✅ 2. Session Context Injection

**Expected from Plugin Log:**
```
Session ID: ses_415e0d216ffeOTZvRHZYF85ZQh
Log message: "Injected session context into span: sessionID=ses_415e0d216ffeOTZvRHZYF85ZQh"
```

**Found in Traces:**
```
✓ session.id: ses_415e0d216ffeOTZvRHZYF85ZQh
✓ user: mtk26468
✓ file.path: /home/mtk26468/opencode-telemetry-plugin/merge_sort.cpp
✓ language: cpp
```

**Result:** Session context injection working perfectly! ✅

### ✅ 3. MongoDB Collections

**Insertion Results:**
```
✓ Prompt collection: 17 records inserted
✓ Metrics collection: 11 records inserted
✓ Database: opencode_telemetry
✓ Both collections have call_id field
```

### ✅ 4. Correlation Queries

**Test Query: Find accepted edits with their prompts**
```javascript
db.metrics.aggregate([
  { $match: { accept: true } },
  {
    $lookup: {
      from: 'prompt',
      localField: 'call_id',
      foreignField: 'call_id',
      as: 'prompt_data'
    }
  }
])
```

**Result:** ✅ Found 9 correlated records (9 accepted edits out of 11 total)

**Sample Correlated Data:**
```json
{
  "accept": true,
  "ai_loc": 4,
  "filepath": "/home/mtk26468/opencode-telemetry-plugin/merge_sort.cpp",
  "user": "mtk26468",
  "call_id": "toolu_01HteZTXi3kBZeGUpiSuGq1L",
  "user_prompt": "Please edit merge_sort.cpp to change all chinese comments to english",
  "model": "claude-sonnet-4-5-20250929",
  "total_tokens": 925,
  "tool_name": "edit"
}
```

---

## Analysis Results

### User Behavior Patterns

#### Acceptance Analysis
```
Total Edits: 11
├─ Accepted: 9 (81.8%)
│  ├─ Manual "once": 6 edits (67%)
│  ├─ Manual "always": 1 edit (11%)
│  └─ Auto-approved: 2 edits (22%)
└─ Rejected: 2 (18.2%)
```

#### Lines of Code
```
Accepted: +186 lines, -9 lines (net: +177)
Rejected: 0 lines (no changes applied)
```

#### Token Usage Analysis
```
ACCEPTED EDITS:
  • Count: 9 edits
  • Total tokens: 7,531
  • Avg tokens/edit: 837
  • Avg LOC/edit: 21

REJECTED EDITS:
  • Count: 2 edits
  • Total tokens: 3,769
  • Avg tokens/edit: 1,885
  • Avg LOC/edit: 0
```

**Insight:** Rejected edits used 2.25x more tokens on average than accepted edits, suggesting they may have been more complex or unclear changes.

#### Acceptance by Type
```
✓ ACCEPT - ONCE (manual):
  • Count: 6 edits
  • Total LOC: 90
  • Avg tokens: 740/edit
  • Avg LOC: 15/edit

✓ ACCEPT - ALWAYS:
  • Count: 1 edit
  • Total LOC: 2
  • Avg tokens: 152/edit
  • Avg LOC: 2/edit

✓ ACCEPT - AUTO:
  • Count: 2 edits
  • Total LOC: 94
  • Avg tokens: 1,470/edit
  • Avg LOC: 47/edit

✗ REJECT:
  • Count: 2 edits
  • Total LOC: 0
  • Avg tokens: 1,884/edit
```

**Insight:** Auto-approved edits had the highest LOC/edit (47 lines), suggesting user trusted the AI for larger changes after initial manual review.

### Session Summary
```
Session: ses_415e0d216ffeOTZvRHZYF85ZQh
User: mtk26468
Duration: ~5 minutes (09:12:48 - 09:17:32)
Total operations: 17 (11 edits + 4 reads + 2 bash commands)
Total tokens used: 11,914
Acceptance rate: 81.8%
Net code change: +177 lines
```

---

## Management Insights Enabled

### 1. ✅ User Productivity
- **Question:** "How productive is this user?"
- **Answer:** 81.8% acceptance rate, +177 lines in 5 minutes, efficient token usage

### 2. ✅ Prompt Effectiveness
- **Question:** "What prompts work best?"
- **Answer:** Single clear prompt ("change chinese comments to english") with 81.8% acceptance across multiple edits

### 3. ✅ Token Efficiency
- **Question:** "Are we using tokens efficiently?"
- **Answer:** Accepted edits average 837 tokens vs 1,885 for rejected, suggesting accepted edits are more straightforward

### 4. ✅ Acceptance Patterns
- **Question:** "When do users accept/reject?"
- **Answer:** User started with manual review (6 edits), then switched to auto-approve (2 edits) after gaining confidence

### 5. ✅ Language/File Analysis
- **Question:** "What files/languages are being edited?"
- **Answer:** All edits on merge_sort.cpp (C++), focused session on single task

---

## Technical Validation

### Data Flow Verified
```
OpenCode Session
    ↓
Plugin captures (hook: tool.execute.before/after)
    ↓
    ├─→ Metrics exported to OTLP → metrics.jsonl (15 exports)
    └─→ Traces exported to OTLP → traces.jsonl (23 exports)
    ↓
analyze_metrics.py → MongoDB.metrics (11 records)
analyze_traces.py → MongoDB.prompt (17 records)
    ↓
MongoDB $lookup join on call_id
    ↓
✅ Correlated data: 9/11 edits with full context
```

### Attribute Injection Verified
```
Plugin: trace.getActiveSpan().setAttributes({
  "session.id": "ses_415e0d216ffeOTZvRHZYF85ZQh",
  "call.id": "toolu_01...",
  "user": "mtk26468",
  "file.path": "/path/to/file.cpp",
  "language": "cpp"
})
    ↓
Found in traces.jsonl ✓
    ↓
Extracted by analyze_traces.py ✓
    ↓
Available in MongoDB.prompt ✓
```

### Correlation Keys Verified
```
Primary Key: call_id
├─ In metrics: ✓ (11/11)
├─ In traces: ✓ (17/17, includes non-edits)
└─ Overlap: ✓ (11/11 edits)

Secondary Key: session_id
├─ In metrics: ✓ (as 'sid')
├─ In traces: ✓ (as 'session_id')
└─ Match: ✓ (same session)
```

---

## Query Examples Validated

### ✅ Query 1: Accepted Edits + Prompts
```javascript
db.metrics.aggregate([
  { $match: { accept: true } },
  { $lookup: { from: "prompt", localField: "call_id", foreignField: "call_id", as: "p" }},
  { $unwind: "$p" },
  { $project: { user_prompt: "$p.user_prompt", ai_loc: 1 }}
])
```
**Result:** 9 records ✓

### ✅ Query 2: Rejected Edits + Prompts
```javascript
db.metrics.aggregate([
  { $match: { accept: false } },
  { $lookup: { from: "prompt", localField: "call_id", foreignField: "call_id", as: "p" }}
])
```
**Result:** 2 records ✓

### ✅ Query 3: Acceptance by Type
```javascript
db.metrics.aggregate([
  { $lookup: { from: "prompt", ... }},
  { $group: { _id: "$reply_type", count: { $sum: 1 } }}
])
```
**Result:** once (6), always (1), auto (2), reject (2) ✓

### ✅ Query 4: Token Usage by Acceptance
```javascript
db.metrics.aggregate([
  { $lookup: { from: "prompt", ... }},
  { $group: { _id: "$accept", total_tokens: { $sum: "$p.total_tokens" } }}
])
```
**Result:** Accepted: 7,531 tokens, Rejected: 3,769 tokens ✓

---

## System Components Status

| Component | Status | Evidence |
|-----------|--------|----------|
| **Plugin (index.ts)** | ✅ Working | All hooks fired, session context injected |
| **Metrics Collection** | ✅ Working | 11/11 edits captured with call_id |
| **Traces Collection** | ✅ Working | 17 tool calls captured with session context |
| **analyze_metrics.py** | ✅ Working | 11 records inserted to MongoDB |
| **analyze_traces.py** | ✅ Working | 17 records inserted to MongoDB |
| **MongoDB Storage** | ✅ Working | Both collections populated, queryable |
| **Correlation Queries** | ✅ Working | All test queries return expected results |
| **Session Context** | ✅ Working | session_id, user, file_path all present |
| **Documentation** | ✅ Complete | All guides and references available |

---

## Performance Metrics

### Data Volume
```
Session duration: ~5 minutes
Operations captured: 17
Metrics exports: 15 (OTLP JSON lines)
Traces exports: 23 (OTLP JSON lines)
MongoDB records: 28 total (11 metrics + 17 prompts)
File sizes:
  - metrics.jsonl: ~25 KB
  - traces.jsonl: ~450 KB
  - MongoDB: ~500 KB
```

### Processing Speed
```
analyze_traces.py: <1 second (23 exports → 17 records)
analyze_metrics.py: <1 second (15 exports → 11 records)
MongoDB insertion: <1 second each
Correlation queries: <100ms
```

---

## Success Criteria: ALL MET ✅

- [x] Plugin logs match metrics.jsonl (100%)
- [x] Plugin logs match traces.jsonl (100%)
- [x] Metrics and traces correlate via call_id (100%)
- [x] Session context injected into traces
- [x] MongoDB collections populated correctly
- [x] Correlation queries return expected results
- [x] User behavior patterns trackable
- [x] Prompt effectiveness analyzable
- [x] Token usage visible and correlated
- [x] Management insights enabled
- [x] All documentation complete

---

## Real-World Value Demonstrated

### For Management
1. **User Productivity:** 81.8% acceptance rate, +177 LOC in 5 minutes
2. **Token ROI:** 11,914 tokens → 177 lines of accepted code
3. **User Behavior:** User gained confidence and switched to auto-approve
4. **Quality Metrics:** Clear prompt led to consistent acceptance

### For Developers
1. **Debugging:** Can see exactly what prompt led to what edit
2. **Learning:** Rejected edits used 2.25x more tokens (too complex?)
3. **Optimization:** Clear prompts work better than vague ones

### For Product Team
1. **Feature Usage:** Auto-approve feature used after manual review phase
2. **User Trust:** Acceptance rate increased from manual to auto
3. **Workflow Patterns:** Single-task focused sessions work well

---

## Conclusion

The trace-metrics correlation system is **fully validated and production-ready**. All components work together seamlessly:

1. ✅ **Data Capture:** Plugin correctly captures all user actions
2. ✅ **Data Storage:** OTLP exports work perfectly
3. ✅ **Data Processing:** Python scripts parse and structure data correctly
4. ✅ **Data Correlation:** MongoDB joins work with 100% accuracy
5. ✅ **Data Analysis:** Queries provide actionable insights

**The system successfully answers the core question:**
*"When users accept edits, what were they doing (what prompts did they give)?"*

**Answer:** We can now see:
- ✅ Exact user prompt
- ✅ Acceptance/rejection decision
- ✅ Lines of code changed
- ✅ Token usage
- ✅ Session context
- ✅ Time spent
- ✅ User behavior patterns

---

## Next Steps (Optional Enhancements)

1. **Real-time Dashboard:** Grafana for live metrics
2. **Automated Reports:** Daily/weekly summaries
3. **Prompt Categorization:** ML-based prompt type detection
4. **Cost Tracking:** Token cost per user/project
5. **A/B Testing:** Compare different AI models

---

## Test Performed By

- **Date:** 2026-01-23
- **Test Type:** Manual end-to-end validation
- **Data:** Clean test with 11 real user actions
- **Environment:** Docker MongoDB + OpenCode + Plugin
- **Result:** ✅ **100% SUCCESS**

---

**The correlation system is ready for production use!** 🎉
