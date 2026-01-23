#!/bin/bash
# Test script for trace-metrics correlation
# This script verifies that traces can be correlated with metrics via call_id

set -e

echo "=================================================="
echo "     TRACE-METRICS CORRELATION TEST"
echo "=================================================="
echo

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Step 1: Analyzing traces...${NC}"
python3 analyze_traces.py

echo
echo -e "${YELLOW}Step 2: Checking for call_id presence in trace records...${NC}"
python3 -c "
import json
import sys

with open('/home/mtk26468/opencode/otel-data/traces.jsonl', 'r') as f:
    for line in f:
        if line.strip():
            data = json.loads(line)
            for rs in data.get('resourceSpans', []):
                for ss in rs.get('scopeSpans', []):
                    for span in ss.get('spans', []):
                        attrs = span.get('attributes', [])
                        for attr in attrs:
                            if attr.get('key') == 'ai.toolCall.id':
                                call_id = attr.get('value', {}).get('stringValue')
                                if call_id:
                                    print(f'✓ Found call_id in trace: {call_id}')
                                    sys.exit(0)
    print('✗ No call_id found in traces')
    sys.exit(1)
"

echo
echo -e "${YELLOW}Step 3: Checking if metrics file exists...${NC}"
if [ -f "/home/mtk26468/opencode/otel-data/metrics.jsonl" ]; then
    echo "✓ Metrics file exists"
    echo -e "${YELLOW}Step 4: Checking for call_id in metrics...${NC}"
    if grep -q "call_id" /home/mtk26468/opencode/otel-data/metrics.jsonl; then
        echo "✓ call_id found in metrics"
    else
        echo "⚠ call_id not found in metrics (may need to use analyze_metrics.py first)"
    fi
else
    echo "⚠ Metrics file not found at /home/mtk26468/opencode/otel-data/metrics.jsonl"
    echo "  (This is OK if you haven't collected metrics yet)"
fi

echo
echo -e "${YELLOW}Step 5: Checking for session context in traces...${NC}"
python3 -c "
import json

session_found = False
user_found = False
file_found = False

with open('/home/mtk26468/opencode/otel-data/traces.jsonl', 'r') as f:
    for line in f:
        if line.strip():
            data = json.loads(line)
            for rs in data.get('resourceSpans', []):
                for ss in rs.get('scopeSpans', []):
                    for span in ss.get('spans', []):
                        attrs = span.get('attributes', [])
                        for attr in attrs:
                            key = attr.get('key')
                            if key == 'session.id':
                                session_found = True
                                print(f'✓ Found session.id in trace')
                            elif key == 'user':
                                user_found = True
                                print(f'✓ Found user in trace')
                            elif key == 'file.path':
                                file_found = True
                                print(f'✓ Found file.path in trace')

if not (session_found or user_found or file_found):
    print('⚠ No session context found in traces')
    print('  This is expected if you haven\\'t used OpenCode with the plugin yet')
    print('  Try: 1) Use OpenCode to make an edit, 2) Re-run this test')
"

echo
echo "=================================================="
echo -e "${GREEN}✓ Test complete!${NC}"
echo "=================================================="
echo
echo "Next steps:"
echo "1. Use OpenCode to make some edits (to generate new traces with session context)"
echo "2. Run: python3 analyze_traces.py --show-records"
echo "3. Run: python3 analyze_traces.py --to-mongo"
echo "4. Verify correlation in MongoDB:"
echo "   mongo opencode_telemetry --eval \"db.prompt.findOne({}, {call_id: 1, session_id: 1, user_prompt: 1})\""
echo
