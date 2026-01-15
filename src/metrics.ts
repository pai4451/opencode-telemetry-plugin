import { metrics, type Counter, type Histogram, type Attributes } from "@opentelemetry/api"
import {
  MeterProvider,
  PeriodicExportingMetricReader,
  AggregationTemporality
} from "@opentelemetry/sdk-metrics"
import { OTLPMetricExporter as OTLPGrpcExporter } from "@opentelemetry/exporter-metrics-otlp-grpc"
import { OTLPMetricExporter as OTLPHttpExporter } from "@opentelemetry/exporter-metrics-otlp-http"
import { Resource } from "@opentelemetry/resources"
import { ATTR_SERVICE_NAME, ATTR_SERVICE_VERSION } from "@opentelemetry/semantic-conventions"
import type { MetricsConfig, RecordLOCInput, RecordToolExecutionInput, RecordPermissionInput } from "./types.js"
import * as Logger from "./logger.js"

/**
 * OpenTelemetry metrics collection module
 */

let meterProvider: MeterProvider | undefined
let enabled = false

// Metric instruments
let locAddedCounter: Counter
let locDeletedCounter: Counter
let toolExecutionCounter: Counter
let toolDurationHistogram: Histogram
let permissionRequestCounter: Counter

/**
 * Initialize OpenTelemetry metrics collection
 */
export async function initialize(config: MetricsConfig): Promise<void> {
  if (!config.enabled || !config.endpoint) {
    Logger.log("Metrics disabled or no endpoint configured")
    return
  }

  try {
    // Validate endpoint URL
    try {
      new URL(config.endpoint)
    } catch (error) {
      Logger.error("Invalid metrics endpoint URL", config.endpoint)
      return
    }

    // Create resource with service metadata
    const resource = new Resource({
      [ATTR_SERVICE_NAME]: "opencode",
      [ATTR_SERVICE_VERSION]: "plugin-1.0.0",
      "opencode.plugin": "telemetry",
    })

    // Create exporter based on protocol
    // Use DELTA temporality to only export changes (not cumulative totals)
    const exporter =
      config.protocol === "http"
        ? new OTLPHttpExporter({
            url: config.endpoint,
            headers: config.headers ?? {},
            timeoutMillis: 5000,
            temporalityPreference: AggregationTemporality.DELTA,
          })
        : new OTLPGrpcExporter({
            url: config.endpoint,
            headers: config.headers ?? {},
            timeoutMillis: 5000,
            temporalityPreference: AggregationTemporality.DELTA,
          })

    // Create metric reader with export interval
    const metricReader = new PeriodicExportingMetricReader({
      exporter,
      exportIntervalMillis: config.exportIntervalMillis || 10000,
    })

    // Initialize meter provider
    meterProvider = new MeterProvider({
      resource,
      readers: [metricReader],
    })

    metrics.setGlobalMeterProvider(meterProvider)
    const meter = metrics.getMeter("opencode", "1.0.0")

    // Create metric instruments
    locAddedCounter = meter.createCounter("opencode.tool.loc.added", {
      description: "Lines of code added by AI tools",
      unit: "lines",
    })

    locDeletedCounter = meter.createCounter("opencode.tool.loc.deleted", {
      description: "Lines of code deleted by AI tools",
      unit: "lines",
    })

    toolExecutionCounter = meter.createCounter("opencode.tool.executions", {
      description: "Number of tool executions",
      unit: "executions",
    })

    toolDurationHistogram = meter.createHistogram("opencode.tool.duration", {
      description: "Tool execution duration",
      unit: "milliseconds",
    })

    permissionRequestCounter = meter.createCounter("opencode.permission.requests", {
      description: "Permission requests by reply type",
      unit: "requests",
    })

    enabled = true
    Logger.log("Metrics initialized", config.endpoint)
  } catch (error) {
    Logger.error("Failed to initialize metrics", error)
  }
}

/**
 * Record lines of code added/deleted
 */
export function recordLinesOfCode(input: RecordLOCInput): void {
  if (!enabled) return

  const attributes: Attributes = {
    "tool.name": input.tool,
    "session.id": input.sessionID,
  }

  if (input.language) {
    attributes["language"] = input.language
  }

  if (input.file) {
    attributes["file.path"] = input.file
  }

  if (input.additions > 0) {
    locAddedCounter.add(input.additions, attributes)
  }

  if (input.deletions > 0) {
    locDeletedCounter.add(input.deletions, attributes)
  }
}

/**
 * Record tool execution metrics
 */
export function recordToolExecution(input: RecordToolExecutionInput): void {
  if (!enabled) return

  const attributes: Attributes = {
    "tool.name": input.tool,
    "tool.status": input.status,
    "session.id": input.sessionID,
  }

  if (input.language) {
    attributes["language"] = input.language
  }

  if (input.agent) {
    attributes["agent.name"] = input.agent
  }

  // Record execution count
  toolExecutionCounter.add(1, attributes)

  // Record duration
  toolDurationHistogram.record(input.duration, attributes)
}

/**
 * Record permission request metrics
 */
export function recordPermissionRequest(input: RecordPermissionInput): void {
  if (!enabled) return

  const attributes: Attributes = {
    "permission.name": input.permission,
    "permission.reply": input.reply,
    "session.id": input.sessionID,
  }

  if (input.tool) {
    attributes["tool.name"] = input.tool
  }

  if (input.language) {
    attributes["language"] = input.language
  }

  permissionRequestCounter.add(1, attributes)
}

/**
 * Shutdown metrics collection and flush pending metrics
 */
export async function shutdown(): Promise<void> {
  if (!enabled || !meterProvider) return

  try {
    Logger.log("Shutting down metrics, forcing flush...")
    await meterProvider.forceFlush()
    await meterProvider.shutdown()
    Logger.log("Metrics shutdown complete")
  } catch (error) {
    Logger.error("Failed to shutdown metrics", error)
  }
}
