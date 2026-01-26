import type { Plugin } from "@opencode-ai/plugin"
import * as os from "os"
import * as Metrics from "./metrics.js"
import * as Traces from "./traces.js"
import * as Correlation from "./correlation.js"
import { inferLanguage } from "./language-map.js"
import type { MetricsConfig, TracesConfig } from "./types.js"
import * as Logger from "./logger.js"
import * as Config from "./config.js"
import { trace } from "@opentelemetry/api"

/**
 * Global config state populated from config hook for use in all metrics
 */
const globalConfig = {
  model: "unknown",
  user: os.userInfo().username,
  version: "1.0.0",
}

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

      // Populate global config from OpenCode config
      const configAny = config as any
      if (configAny.model) {
        globalConfig.model = configAny.model
        Logger.debug("Model set from config", globalConfig.model)
      }

      // Log entire experimental object for debugging
      if (configAny.experimental) {
        Logger.debug("experimental object", JSON.stringify(configAny.experimental, null, 2))
      }

      // Use OpenCode's built-in openTelemetry flag
      const openTelemetryEnabled = configAny.experimental?.openTelemetry
      Logger.debug("openTelemetry enabled", openTelemetryEnabled)

      if (!openTelemetryEnabled) {
        Logger.log("OpenTelemetry disabled in config (set experimental.openTelemetry = true to enable)")
        return
      }

      // Parse configuration from environment variables
      // Note: Custom config fields in opencode.jsonc don't work due to strict Zod schema
      // We only support environment variables: OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_EXPORTER_OTLP_PROTOCOL
      const metricsConfig = Config.parseMetricsConfig()
      const tracesConfig = Config.parseTracesConfig()

      Logger.log("Initializing metrics with config:")
      Logger.log(`  Endpoint: ${metricsConfig.endpoint}`)
      Logger.log(`  Protocol: ${metricsConfig.protocol}`)
      Logger.log(`  Export interval: ${metricsConfig.exportIntervalMillis}ms`)
      Logger.log(`  Source: ${process.env.OTEL_EXPORTER_OTLP_ENDPOINT ? 'Environment variables' : 'Defaults'}`)
      Logger.log(`Global config: model=${globalConfig.model}, user=${globalConfig.user}, version=${globalConfig.version}`)

      await Metrics.initialize(metricsConfig)

      Logger.log("Initializing traces with config:")
      Logger.log(`  Endpoint: ${tracesConfig.endpoint}`)
      Logger.log(`  Protocol: ${tracesConfig.protocol}`)
      Logger.log(`  Source: ${process.env.OTEL_EXPORTER_OTLP_ENDPOINT ? 'Environment variables' : 'Defaults'}`)

      await Traces.initialize(tracesConfig)
    },

    "tool.execute.before": async (input, output) => {
      Logger.debug(`tool.execute.before: tool=${input.tool}, callID=${input.callID}`)

      // Inject session context into active AI SDK span
      const activeSpan = trace.getActiveSpan()
      if (activeSpan) {
        activeSpan.setAttributes({
          "session.id": input.sessionID,
          "call.id": input.callID,
          "tool.name": input.tool,
          "user": globalConfig.user,
          "opencode.version": globalConfig.version,
        })
        Logger.debug(`Injected session context into span: sessionID=${input.sessionID}, callID=${input.callID}`)
      }

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

        // Add file context to active span if available
        const activeSpan = trace.getActiveSpan()
        if (activeSpan) {
          activeSpan.setAttributes({
            "file.path": filediff.file,
            "language": language,
            "loc.added": filediff.additions || 0,
            "loc.deleted": filediff.deletions || 0,
          })
          Logger.debug(`Added file context to span: file=${filediff.file}, language=${language}`)
        }
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
          // New attributes for final JSON conversion
          model: globalConfig.model,
          user: globalConfig.user,
          version: globalConfig.version,
          callID: input.callID,
        })
        Logger.log(`LOC recorded: +${filediff.additions || 0} -${filediff.deletions || 0} (tool=${input.tool}, language=${language}, callID=${input.callID})`)

        // Check if this edit was auto-approved (no permission event was triggered)
        // If permission was NOT asked, record an implicit "accept" with autoApproveEdit=true
        const permissionWasAsked = Correlation.wasPermissionAskedForCall(input.callID)
        if (!permissionWasAsked) {
          Metrics.recordPermissionRequest({
            permission: "edit",
            reply: "auto",  // Auto-approved = no dialog shown, system auto-approved
            sessionID: input.sessionID,
            tool: input.tool,
            language,
            model: globalConfig.model,
            user: globalConfig.user,
            version: globalConfig.version,
            callID: input.callID,
            filepath: filediff.file,
            autoApproveEdit: true,  // Permission was NOT asked, so auto_approve_edit = true
          })
          Logger.log(`AUTO-APPROVED EDIT recorded: auto (tool=${input.tool}, language=${language}, callID=${input.callID}, filepath=${filediff.file})`)
        }
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

        // Extract filepath from metadata if available
        // The actual field name is "filepath" (no underscore), not "file_path"
        const filepath = props?.metadata?.filepath
          || props?.tool?.metadata?.filepath
          || props?.metadata?.file_path
          || props?.tool?.input?.file_path
          || undefined

        // Store full permission info for later retrieval in permission.replied
        // The permission.replied event may NOT have permission/tool fields, so we store them here
        Correlation.registerPermissionAsked(
          props.id,
          props.permission,
          props.sessionID,
          props.tool?.callID,
          filepath,
        )
        Logger.debug(`Permission request stored: requestID=${props.id}, permission=${props.permission}, callID=${props.tool?.callID}, filepath=${filepath}`)
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

        // Use the original reply value from OpenCode: "once", "always", or "reject"
        // This is clearer than mapping to different names
        const decision = props.reply  // "once", "always", or "reject"

        // Try to get tool name, language, and filepath from tool execution context
        let toolName = "unknown"
        let language = "unknown"
        let filepath = permissionInfo.filepath  // Start with filepath from permission.asked
        if (permissionInfo.callID) {
          const ctx = Correlation.getContextForCall(permissionInfo.callID)
          if (ctx) {
            toolName = ctx.tool
            language = ctx.language || "unknown"
            // If we have filediff from context, use that filepath
            if (ctx.filediff?.file && !filepath) {
              filepath = ctx.filediff.file
            }
            Logger.debug(`Context found for callID=${permissionInfo.callID}: tool=${toolName}, language=${language}, filepath=${filepath}`)
          } else {
            Logger.debug(`No context found for callID=${permissionInfo.callID}`)
          }
          Correlation.registerPermissionReplied(props.requestID, decision)
        }

        // Record metric with the permission info we stored from permission.asked
        // autoApproveEdit is FALSE because permission WAS asked (user manually approved)
        // autoApproveEdit is TRUE when permission was NOT asked (auto-approved)
        Metrics.recordPermissionRequest({
          permission: permissionInfo.permission,
          reply: decision,
          sessionID: permissionInfo.sessionID,
          tool: toolName,
          language,
          // New attributes for final JSON conversion
          model: globalConfig.model,
          user: globalConfig.user,
          version: globalConfig.version,
          callID: permissionInfo.callID,
          filepath,
          autoApproveEdit: false,  // Permission was asked, so auto_approve_edit = false (manual approval)
        })

        // Clear summary log line (similar to LOC: "LOC recorded: +X -Y")
        Logger.log(`PERMISSION RECORDED: ${permissionInfo.permission} -> ${decision} (tool=${toolName}, session=${permissionInfo.sessionID?.slice(0,12)}..., filepath=${filepath})`)
      }
    },
  }
}

export default plugin
