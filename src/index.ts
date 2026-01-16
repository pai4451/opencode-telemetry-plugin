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

      // Only log permission-related events (avoid spam from other events)
      if (event.type?.startsWith("permission.")) {
        Logger.debug(`Event received: ${event.type}`)
      }

      if (event.type === "permission.asked") {
        const props = event.properties
        // Detailed logging similar to LOC logging
        Logger.log(`PERMISSION ASKED: permission=${props?.permission}, requestID=${props?.id}, hasToolCallID=${!!props?.tool?.callID}`)
        Logger.debug("permission.asked full props", JSON.stringify(props, null, 2))

        // Store full permission info for later retrieval in permission.replied
        // The permission.replied event may NOT have permission/tool fields, so we store them here
        Correlation.registerPermissionAsked(
          props.id,
          props.permission,
          props.sessionID,
          props.tool?.callID,
        )
        Logger.debug(`Permission request stored: requestID=${props.id}, permission=${props.permission}, callID=${props.tool?.callID}`)
      }

      if (event.type === "permission.replied") {
        const props = event.properties

        // Detailed logging similar to LOC logging (Logger.log for important events)
        Logger.log(`PERMISSION REPLIED: reply=${props?.reply}, requestID=${props?.requestID}`)
        Logger.debug("permission.replied full props", JSON.stringify(props, null, 2))

        // Get the stored permission info from permission.asked event
        // The permission.replied event may NOT have permission/tool fields!
        const permissionInfo = Correlation.getPermissionRequest(props?.requestID)

        if (!permissionInfo) {
          Logger.error(`No permission request found for requestID=${props?.requestID} - cannot record metric`)
          return
        }

        Logger.debug(`Found permission info: permission=${permissionInfo.permission}, callID=${permissionInfo.callID}`)

        // Map reply to decision
        const decision = props.reply === "reject" ? "reject"
                       : props.reply === "always" ? "auto_accept"
                       : "accept"

        // Try to get tool name and language from tool execution context
        let toolName = "unknown"
        let language = "unknown"
        if (permissionInfo.callID) {
          const ctx = Correlation.getContextForCall(permissionInfo.callID)
          if (ctx) {
            toolName = ctx.tool
            language = ctx.language || "unknown"
            Logger.debug(`Context found for callID=${permissionInfo.callID}: tool=${toolName}, language=${language}`)
          } else {
            Logger.debug(`No context found for callID=${permissionInfo.callID}`)
          }
          Correlation.registerPermissionReplied(props.requestID, decision)
        }

        // Record metric with the permission info we stored from permission.asked
        Metrics.recordPermissionRequest({
          permission: permissionInfo.permission,
          reply: decision,
          sessionID: permissionInfo.sessionID,
          tool: toolName,
          language,
        })

        // Clear summary log line (similar to LOC: "LOC recorded: +X -Y")
        Logger.log(`PERMISSION RECORDED: ${permissionInfo.permission} -> ${decision} (tool=${toolName}, session=${permissionInfo.sessionID?.slice(0,12)}...)`)
      }
    },
  }
}

export default plugin
