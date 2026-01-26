import type { MetricsConfig, TracesConfig } from "./types.js"

/**
 * Parse metrics configuration from environment variables only.
 *
 * OpenCode's config schema uses Zod strict mode, which strips unknown fields.
 * Custom config fields added by plugins cannot be passed through the config file.
 * Therefore, we only support environment variables for configuration.
 *
 * Environment variables (standard OpenTelemetry):
 * - OTEL_EXPORTER_OTLP_ENDPOINT: Base endpoint URL (applies to both metrics and traces)
 * - OTEL_EXPORTER_OTLP_METRICS_ENDPOINT: Override for metrics endpoint
 * - OTEL_EXPORTER_OTLP_PROTOCOL: Protocol (http or grpc)
 */
export function parseMetricsConfig(): MetricsConfig {
  let endpoint =
    process.env.OTEL_EXPORTER_OTLP_METRICS_ENDPOINT ||
    process.env.OTEL_EXPORTER_OTLP_ENDPOINT ||
    "http://localhost:4318" // HTTP default port

  const protocol =
    (process.env.OTEL_EXPORTER_OTLP_PROTOCOL as "grpc" | "http") ||
    "http" // Default to HTTP

  // HTTP protocol requires /v1/metrics path, gRPC does not
  if (protocol === "http" && !endpoint.endsWith("/v1/metrics")) {
    // Remove trailing slash if present
    endpoint = endpoint.replace(/\/$/, "")
    endpoint = `${endpoint}/v1/metrics`
  }

  const exportIntervalMillis = 5000

  return {
    enabled: true,
    endpoint,
    protocol,
    exportIntervalMillis,
  }
}

/**
 * Parse traces configuration from environment variables only.
 *
 * Environment variables (standard OpenTelemetry):
 * - OTEL_EXPORTER_OTLP_ENDPOINT: Base endpoint URL (applies to both metrics and traces)
 * - OTEL_EXPORTER_OTLP_TRACES_ENDPOINT: Override for traces endpoint
 * - OTEL_EXPORTER_OTLP_PROTOCOL: Protocol (http or grpc)
 */
export function parseTracesConfig(): TracesConfig {
  let endpoint =
    process.env.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT ||
    process.env.OTEL_EXPORTER_OTLP_ENDPOINT ||
    "http://localhost:4318"

  const protocol =
    (process.env.OTEL_EXPORTER_OTLP_PROTOCOL as "grpc" | "http") ||
    "http"

  // HTTP protocol requires /v1/traces path, gRPC does not
  if (protocol === "http" && !endpoint.endsWith("/v1/traces")) {
    // Remove trailing slash if present
    endpoint = endpoint.replace(/\/$/, "")
    endpoint = `${endpoint}/v1/traces`
  }

  return {
    enabled: true,
    endpoint,
    protocol,
  }
}
