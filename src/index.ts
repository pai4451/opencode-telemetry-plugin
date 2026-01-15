import type { Plugin } from "@opencode-ai/plugin"
import * as Metrics from "./metrics.js"
import * as Correlation from "./correlation.js"
import { inferLanguage } from "./language-map.js"
import type { MetricsConfig } from "./types.js"
import * as Logger from "./logger.js"

/**
 * OpenCode OpenTelemetry Plugin
 *
 * Collects telemetry metrics without modifying OpenCode's source code:
 * - Lines of code added/deleted (LOC)
 * - Accept/reject decisions
 * - Tool execution metrics
 * - Filepath and programming language
 *
 * Exports to any OTLP backend (Grafana, Honeycomb, etc.)
 */
const plugin: Plugin = async (input) => {
  Logger.initLogger()
  Logger.log("Plugin loaded for project", input.directory)
  console.log(`[opencode-telemetry] Plugin loaded. Logs: ${Logger.getLogFilePath()}`)

  return {
    config: async (config) => {
      Logger.log("Config hook called")
      Logger.debug("Config object keys", Object.keys(config || {}))

      // Log entire experimental object for debugging
      if ((config as any).experimental) {
        Logger.debug("experimental object", JSON.stringify((config as any).experimental, null, 2))
      }

      // Use OpenCode's built-in openTelemetry flag
      const openTelemetryEnabled = (config as any).experimental?.openTelemetry
      Logger.debug("openTelemetry enabled", openTelemetryEnabled)

      if (!openTelemetryEnabled) {
        Logger.log("OpenTelemetry disabled in config (set experimental.openTelemetry = true to enable)")
        return
      }

      // Use default OTEL configuration
      // Export interval: 5 seconds - responsive with DELTA mode (no spam!)
      const metricsConfig: MetricsConfig = {
        enabled: true,
        endpoint: "http://localhost:4317",
        protocol: "grpc",
        exportIntervalMillis: 5000, // 5 seconds
      }

      Logger.log("Initializing metrics with openTelemetry enabled")
      await Metrics.initialize(metricsConfig)
    },

    "tool.execute.before": async (input, output) => {
      Logger.debug(`tool.execute.before: tool=${input.tool}, callID=${input.callID}`)
      Correlation.registerToolStart(input.callID, input.tool, input.sessionID)
    },

    "tool.execute.after": async (input, output) => {
      Logger.debug(`tool.execute.after: tool=${input.tool}, callID=${input.callID}`)

      const ctx = Correlation.getContextForCall(input.callID)
      if (!ctx) {
        Logger.error(`No context found for callID=${input.callID}`)
        return
      }

      const duration = Date.now() - ctx.startTime
      const metadata = output.metadata || {}
      const filediff = metadata.filediff

      Logger.debug(`metadata keys: ${Object.keys(metadata).join(", ")}`)
      Logger.debug(`filediff present: ${!!filediff}`)

      if (filediff) {
        Logger.log(`filediff: file=${filediff.file}, additions=${filediff.additions}, deletions=${filediff.deletions}`)
      }

      let language = "unknown"
      let files: string[] = []

      if (filediff?.file) {
        files = [filediff.file]
        language = inferLanguage(filediff.file)
        Logger.debug(`language inferred: ${language}`)
      }

      Metrics.recordToolExecution({
        tool: input.tool,
        status: "success",
        duration,
        sessionID: input.sessionID,
        language,
      })
      Logger.debug(`Recorded tool execution metric`)

      if (filediff && (filediff.additions !== undefined || filediff.deletions !== undefined)) {
        Metrics.recordLinesOfCode({
          tool: input.tool,
          additions: filediff.additions || 0,
          deletions: filediff.deletions || 0,
          sessionID: input.sessionID,
          language,
          file: filediff.file,
        })
        Logger.log(`LOC recorded: +${filediff.additions || 0} -${filediff.deletions || 0} (tool=${input.tool}, language=${language})`)
      }

      Correlation.registerToolEnd(input.callID, { filediff, files, language })
    },

    event: async (input) => {
      const event = input.event as any

      if (event.type === "permission.asked") {
        const props = event.properties
        if (props?.tool?.callID) {
          Correlation.registerPermissionAsked(props.id, props.tool.callID)
        }
      }

      if (event.type === "permission.replied") {
        const props = event.properties
        const callID = Correlation.getCallIDForRequest(props?.requestID)
        if (!callID) return

        const decision = props.reply === "reject" ? "reject" : props.reply === "always" ? "auto_accept" : "accept"
        const ctx = Correlation.getContextForCall(callID)
        if (!ctx) return

        Metrics.recordPermissionRequest({
          permission: props.permission || "unknown",
          reply: decision,
          sessionID: props.sessionID,
          tool: ctx.tool,
          language: ctx.language,
        })

        Correlation.registerPermissionReplied(props.requestID, decision)
      }
    },
  }
}

export default plugin
