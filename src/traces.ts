import { NodeSDK } from "@opentelemetry/sdk-node"
import { OTLPTraceExporter as OTLPTraceExporterGrpc } from "@opentelemetry/exporter-trace-otlp-grpc"
import { OTLPTraceExporter as OTLPTraceExporterHttp } from "@opentelemetry/exporter-trace-otlp-http"
import { Resource } from "@opentelemetry/resources"
import { ATTR_SERVICE_NAME, ATTR_SERVICE_VERSION } from "@opentelemetry/semantic-conventions"
import type { TracesConfig } from "./types.js"
import * as Logger from "./logger.js"

let sdk: NodeSDK | undefined
let initialized = false

/**
 * Initialize OpenTelemetry tracing for AI SDK spans
 */
export async function initialize(config: TracesConfig): Promise<void> {
  if (!config.enabled || !config.endpoint || initialized) {
    Logger.log("Traces disabled, already initialized, or no endpoint")
    return
  }

  try {
    // Create resource with service metadata
    const resource = new Resource({
      [ATTR_SERVICE_NAME]: "opencode",
      [ATTR_SERVICE_VERSION]: "plugin-1.0.0",
      "opencode.plugin": "telemetry",
    })

    // Create OTLP trace exporter based on protocol
    const traceExporter =
      config.protocol === "http"
        ? new OTLPTraceExporterHttp({
            url: config.endpoint,
            headers: config.headers ?? {},
            timeoutMillis: 5000,
          })
        : new OTLPTraceExporterGrpc({
            url: config.endpoint,
            headers: config.headers ?? {},
            timeoutMillis: 5000,
          })

    // Initialize NodeSDK
    sdk = new NodeSDK({
      resource,
      traceExporter,
    })

    // Start the SDK
    await sdk.start()

    initialized = true
    Logger.log("Traces initialized", config.endpoint)
  } catch (error) {
    Logger.error("Failed to initialize traces", error)
  }
}

/**
 * Shutdown tracing and flush pending spans
 */
export async function shutdown(): Promise<void> {
  if (!initialized || !sdk) return

  try {
    Logger.log("Shutting down traces, forcing flush...")
    await sdk.shutdown()
    Logger.log("Traces shutdown complete")
  } catch (error) {
    Logger.error("Failed to shutdown traces", error)
  }
}
