import type { CallContext, FileDiff } from "./types.js"

/**
 * Permission request info stored from permission.asked event
 */
interface PermissionRequestInfo {
  requestID: string
  permission: string
  callID?: string
  sessionID: string
  timestamp: number
}

/**
 * Maps for correlating tool executions with permission decisions
 */
const callContext = new Map<string, CallContext>()
const requestToCall = new Map<string, string>() // requestID → callID
const callToRequest = new Map<string, string>() // callID → requestID
const permissionRequests = new Map<string, PermissionRequestInfo>() // requestID → permission info

/**
 * Maximum age for context entries (1 minute)
 */
const MAX_CONTEXT_AGE = 60000

/**
 * Register the start of a tool execution
 */
export function registerToolStart(callID: string, tool: string, sessionID: string): void {
  callContext.set(callID, {
    tool,
    sessionID,
    startTime: Date.now(),
  })
}

/**
 * Register the end of a tool execution with metadata
 */
export function registerToolEnd(
  callID: string,
  metadata: {
    filediff?: FileDiff
    files?: string[]
    language?: string
  },
): void {
  const ctx = callContext.get(callID)
  if (!ctx) return

  if (metadata.filediff) {
    ctx.filediff = metadata.filediff
  }
  if (metadata.files) {
    ctx.files = metadata.files
  }
  if (metadata.language) {
    ctx.language = metadata.language
  }
}

/**
 * Register a permission request and link it to a tool call
 * Stores full permission info for later retrieval in permission.replied
 */
export function registerPermissionAsked(
  requestID: string,
  permission: string,
  sessionID: string,
  callID?: string,
): void {
  // Store full permission request info
  permissionRequests.set(requestID, {
    requestID,
    permission,
    callID,
    sessionID,
    timestamp: Date.now(),
  })

  // Also maintain the callID mappings if available
  if (callID) {
    requestToCall.set(requestID, callID)
    callToRequest.set(callID, requestID)
  }
}

/**
 * Get permission request info by requestID
 */
export function getPermissionRequest(requestID: string): PermissionRequestInfo | undefined {
  return permissionRequests.get(requestID)
}

/**
 * Register a permission reply and update the call context
 */
export function registerPermissionReplied(
  requestID: string,
  decision: "accept" | "reject" | "auto_accept",
): void {
  const callID = requestToCall.get(requestID)
  if (!callID) return

  const ctx = callContext.get(callID)
  if (ctx) {
    ctx.decision = decision
  }
}

/**
 * Get the call context for a given callID
 */
export function getContextForCall(callID: string): CallContext | undefined {
  return callContext.get(callID)
}

/**
 * Get the callID associated with a permission request
 */
export function getCallIDForRequest(requestID: string): string | undefined {
  return requestToCall.get(requestID)
}

/**
 * Clean up old context entries to prevent memory leaks
 */
export function cleanup(): void {
  const now = Date.now()
  const staleCallIDs: string[] = []
  const staleRequestIDs: string[] = []

  for (const [callID, ctx] of callContext.entries()) {
    if (now - ctx.startTime > MAX_CONTEXT_AGE) {
      staleCallIDs.push(callID)
    }
  }

  for (const [requestID, info] of permissionRequests.entries()) {
    if (now - info.timestamp > MAX_CONTEXT_AGE) {
      staleRequestIDs.push(requestID)
    }
  }

  for (const callID of staleCallIDs) {
    callContext.delete(callID)

    // Clean up related mappings
    const requestID = callToRequest.get(callID)
    if (requestID) {
      requestToCall.delete(requestID)
      callToRequest.delete(callID)
    }
  }

  for (const requestID of staleRequestIDs) {
    permissionRequests.delete(requestID)
    // Also clean up callID mappings if they exist
    const callID = requestToCall.get(requestID)
    if (callID) {
      requestToCall.delete(requestID)
      callToRequest.delete(callID)
    }
  }
}

/**
 * Start periodic cleanup
 */
const cleanupInterval = setInterval(cleanup, 30000) // Run every 30 seconds

/**
 * Stop periodic cleanup (for testing or shutdown)
 */
export function stopCleanup(): void {
  clearInterval(cleanupInterval)
}

/**
 * Get current stats for debugging
 */
export function getStats(): {
  callContextSize: number
  requestToCallSize: number
  callToRequestSize: number
  permissionRequestsSize: number
} {
  return {
    callContextSize: callContext.size,
    requestToCallSize: requestToCall.size,
    callToRequestSize: callToRequest.size,
    permissionRequestsSize: permissionRequests.size,
  }
}
