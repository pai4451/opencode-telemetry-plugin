#!/bin/bash
# End-to-end demonstration of trace-metrics correlation
# This script processes both traces and metrics, then shows example correlations

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "============================================================"
echo "     TRACE-METRICS CORRELATION DEMO"
echo "============================================================"
echo

# Check if MongoDB is available
if ! command -v mongosh &> /dev/null && ! command -v mongo &> /dev/null; then
    echo -e "${YELLOW}⚠ MongoDB CLI not found. Correlation queries will be skipped.${NC}"
    echo "  Install MongoDB to run full demo: https://www.mongodb.com/docs/manual/installation/"
    echo
    SKIP_MONGO=1
else
    SKIP_MONGO=0
    # Determine which MongoDB CLI to use
    if command -v mongosh &> /dev/null; then
        MONGO_CLI="mongosh"
    else
        MONGO_CLI="mongo"
    fi
fi

# Step 1: Process Traces
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Step 1: Processing Traces${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo

if [ -f "/home/mtk26468/opencode/otel-data/traces.jsonl" ]; then
    python3 analyze_traces.py

    if [ $SKIP_MONGO -eq 0 ]; then
        echo
        echo -e "${YELLOW}Sending traces to MongoDB...${NC}"
        python3 analyze_traces.py --to-mongo
    fi
else
    echo -e "${RED}✗ Traces file not found at /home/mtk26468/opencode/otel-data/traces.jsonl${NC}"
    echo "  Please use OpenCode with telemetry enabled to generate traces."
    exit 1
fi

# Step 2: Process Metrics
echo
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Step 2: Processing Metrics${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo

if [ -f "/home/mtk26468/opencode/otel-data/metrics.jsonl" ]; then
    python3 analyze_metrics.py

    if [ $SKIP_MONGO -eq 0 ]; then
        echo
        echo -e "${YELLOW}Sending metrics to MongoDB...${NC}"
        python3 analyze_metrics.py --to-mongo
    fi
else
    echo -e "${YELLOW}⚠ Metrics file not found. Skipping metrics processing.${NC}"
    echo "  This is OK if you haven't collected acceptance/rejection metrics yet."
fi

# Step 3: Verify Correlation Keys
echo
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Step 3: Verifying Correlation Keys${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo

if [ $SKIP_MONGO -eq 0 ]; then
    echo "Checking for matching call_ids..."
    echo

    # Get sample call_id from each collection
    echo "Sample call_id from prompt collection:"
    $MONGO_CLI --quiet opencode_telemetry --eval "db.prompt.findOne({}, {call_id: 1, _id: 0})" || true

    echo
    echo "Sample call_id from metrics collection:"
    $MONGO_CLI --quiet opencode_telemetry --eval "db.metrics.findOne({}, {call_id: 1, _id: 0})" || true

    echo
    echo "Count of records in each collection:"
    echo -n "  Prompts: "
    $MONGO_CLI --quiet opencode_telemetry --eval "db.prompt.count()" || true
    echo -n "  Metrics: "
    $MONGO_CLI --quiet opencode_telemetry --eval "db.metrics.count()" || true
else
    echo "MongoDB not available. Skipping verification."
fi

# Step 4: Example Correlation Query
echo
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Step 4: Example Correlation Query${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo

if [ $SKIP_MONGO -eq 0 ]; then
    echo "Finding prompts for accepted edits..."
    echo

    $MONGO_CLI --quiet opencode_telemetry --eval '
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
          _id: 0,
          call_id: 1,
          accept: 1,
          ai_loc: 1,
          user_prompt: "$prompt_data.user_prompt",
          model: "$prompt_data.model",
          total_tokens: "$prompt_data.total_tokens"
        }
      },
      { $limit: 3 }
    ]).forEach(printjson)
    ' || echo -e "${YELLOW}⚠ No correlated data found. This is expected if metrics collection is empty.${NC}"

    echo
    echo -e "${GREEN}✓ Correlation query complete!${NC}"
else
    echo "MongoDB not available. Skipping correlation query."
    echo
    echo "To run correlation queries manually, use:"
    echo "  mongosh opencode_telemetry"
    echo
    echo "Example query:"
    cat << 'EOF'
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
          call_id: 1,
          accept: 1,
          ai_loc: 1,
          user_prompt: "$prompt_data.user_prompt",
          model: "$prompt_data.model",
          total_tokens: "$prompt_data.total_tokens"
        }
      },
      { $limit: 5 }
    ])
EOF
fi

# Summary
echo
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Summary${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo
echo -e "${GREEN}✓ Trace-metrics correlation system is ready!${NC}"
echo
echo "What you can do now:"
echo "  1. Use OpenCode to make edits (to generate new traces with session context)"
echo "  2. Review the MongoDB collections:"
echo "     - Collection 'metrics': acceptance/rejection decisions"
echo "     - Collection 'prompt': AI prompts and completions"
echo "  3. Run correlation queries (see CORRELATION_GUIDE.md for examples)"
echo "  4. Analyze user productivity, prompt effectiveness, and more"
echo
echo "Documentation:"
echo "  - Full guide: CORRELATION_GUIDE.md"
echo "  - Test script: ./test-correlation.sh"
echo
echo "For more examples and query patterns, see:"
echo "  cat CORRELATION_GUIDE.md"
echo

exit 0
