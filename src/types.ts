/**
 * Configuration for OpenTelemetry metrics collection
 */
export interface MetricsConfig {
  enabled: boolean
  endpoint: string
  protocol: "grpc" | "http"
  headers?: Record<string, string>
  exportIntervalMillis?: number
  includeFilepath?: boolean
}

/**
 * Configuration for OpenTelemetry traces collection
 */
export interface TracesConfig {
  enabled: boolean
  endpoint: string
  protocol: "grpc" | "http"
  headers?: Record<string, string>
}

/**
 * File diff information with LOC counts
 */
export interface FileDiff {
  file: string
  additions: number
  deletions: number
  before?: string
  after?: string
}

/**
 * Context information for a tool call
 */
export interface CallContext {
  tool: string
  sessionID: string
  startTime: number
  decision?: "once" | "always" | "auto" | "reject"
  filediff?: FileDiff
  files?: string[]
  language?: string
}

/**
 * Metric recording input for lines of code
 */
export interface RecordLOCInput {
  tool: string
  additions: number
  deletions: number
  sessionID: string
  language?: string
  file?: string
  // New fields for final JSON conversion
  model?: string
  user?: string
  version?: string
  callID?: string
}

/**
 * Metric recording input for tool execution
 */
export interface RecordToolExecutionInput {
  tool: string
  status: "success" | "error" | "rejected"
  duration: number
  sessionID: string
  language?: string
  agent?: string
}

/**
 * Metric recording input for permission requests
 */
export interface RecordPermissionInput {
  permission: string
  reply: "once" | "always" | "auto" | "reject"
  sessionID: string
  tool?: string
  language?: string
  // New fields for final JSON conversion
  model?: string
  user?: string
  version?: string
  callID?: string
  filepath?: string
  autoApproveEdit?: boolean
}
