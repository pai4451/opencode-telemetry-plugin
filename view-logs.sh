#!/bin/bash

# OpenCode Telemetry Plugin Log Viewer

LOG_FILE="$HOME/.local/share/opencode/telemetry-plugin.log"

if [ ! -f "$LOG_FILE" ]; then
    echo "No log file found at: $LOG_FILE"
    echo ""
    echo "The log file will be created when you run OpenCode with the plugin."
    exit 0
fi

echo "=== OpenCode Telemetry Plugin Logs ==="
echo "Log file: $LOG_FILE"
echo "Size: $(du -h "$LOG_FILE" | cut -f1)"
echo "Last modified: $(stat -c %y "$LOG_FILE" 2>/dev/null || stat -f %Sm "$LOG_FILE" 2>/dev/null)"
echo ""

# Check command line argument
case "${1:-tail}" in
    all)
        echo "=== All Logs ==="
        cat "$LOG_FILE"
        ;;
    tail|last)
        echo "=== Last 50 Lines ==="
        tail -50 "$LOG_FILE"
        ;;
    follow|watch|live)
        echo "=== Live Tail (Ctrl+C to exit) ==="
        tail -f "$LOG_FILE"
        ;;
    loc|lines)
        echo "=== LOC Metrics ==="
        grep "LOC recorded" "$LOG_FILE" | tail -20
        ;;
    errors)
        echo "=== Errors ==="
        grep "ERROR:" "$LOG_FILE" | tail -20
        ;;
    summary)
        echo "=== Summary ==="
        echo ""
        echo "Total log entries: $(wc -l < "$LOG_FILE")"
        echo "LOC recordings: $(grep -c "LOC recorded" "$LOG_FILE")"
        echo "Tool executions: $(grep -c "tool.execute.after" "$LOG_FILE")"
        echo "Errors: $(grep -c "ERROR:" "$LOG_FILE")"
        echo ""
        echo "Recent LOC recordings:"
        grep "LOC recorded" "$LOG_FILE" | tail -5
        ;;
    clear|clean)
        echo "Clearing log file..."
        > "$LOG_FILE"
        echo "Log file cleared."
        ;;
    help)
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  tail, last    - Show last 50 lines (default)"
        echo "  all          - Show all logs"
        echo "  follow, live - Follow log in real-time"
        echo "  loc, lines   - Show only LOC recordings"
        echo "  errors       - Show only errors"
        echo "  summary      - Show statistics"
        echo "  clear, clean - Clear the log file"
        echo "  help         - Show this help"
        ;;
    *)
        echo "Unknown command: $1"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac
