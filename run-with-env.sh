#!/bin/bash

# Run OpenCode with OpenTelemetry environment variables
#
# OpenCode's config schema uses strict validation and rejects custom fields.
# This script sets environment variables which bypass schema validation.
#
# Customize the values below for your environment:

export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"
export OTEL_EXPORTER_OTLP_PROTOCOL="http"

# Optional: Separate endpoints for metrics and traces
# export OTEL_EXPORTER_OTLP_METRICS_ENDPOINT="http://metrics-collector:4318"
# export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="http://traces-collector:4318"

echo "========================================="
echo "OpenCode Telemetry Plugin"
echo "========================================="
echo ""
echo "Environment variables:"
echo "  OTEL_EXPORTER_OTLP_ENDPOINT=$OTEL_EXPORTER_OTLP_ENDPOINT"
echo "  OTEL_EXPORTER_OTLP_PROTOCOL=$OTEL_EXPORTER_OTLP_PROTOCOL"
echo ""
echo "Starting OpenCode..."
echo ""
echo "Expected log output:"
echo "  [telemetry-plugin] Initializing metrics with config:"
echo "    Endpoint: http://localhost:4318"
echo "    Protocol: http"
echo "    Source: Environment variables  ← Should show this!"
echo ""

opencode
