# Feasibility Study: Observability for OpenCode Features

**Date:** 2026-02-05
**Scope:** Skills, MCP, Agents, Slash Commands
**Verdict:** Highly Feasible - All features observable via existing plugin hooks

---

## Executive Summary

OpenCode's plugin architecture provides comprehensive hooks and events that enable observability for skills, MCP, agents, and slash commands **without modifying OpenCode's source code**. Your existing telemetry plugin already uses the necessary hooks - you just need to add more event handlers and filtering logic.

---

## Table of Contents

1. [Current Plugin Infrastructure](#current-plugin-infrastructure)
2. [Slash Commands](#1-slash-commands)
3. [Skills (Agent Skills)](#2-skills-agent-skills)
4. [MCP (Model Context Protocol)](#3-mcp-model-context-protocol)
5. [Agents (Task/Subagents)](#4-agents-tasksubagents)
6. [Implementation Details](#implementation-details)
7. [Proposed Metrics](#proposed-metrics)
8. [Key Files Reference](#key-files-reference)

---

## Current Plugin Infrastructure

Your existing telemetry plugin at `/home/mtk26468/opencode-telemetry-plugin/src/index.ts` already uses:

```typescript
const plugin: Plugin = async (input) => {
  return {
    config: async (config) => { ... },

    "tool.execute.before": async (input, output) => { ... },

    "tool.execute.after": async (input, output) => { ... },

    event: async (input) => { ... },  // Receives ALL bus events
  }
}
```

These same hooks can capture data for all features studied.

---

## 1. Slash Commands

### How It Works in OpenCode

**Source Files:**
- Definition: `/home/mtk26468/opencode/packages/opencode/src/command/index.ts`
- Execution: `/home/mtk26468/opencode/packages/opencode/src/session/prompt.ts` (lines 1480-1594)

**Flow:**
1. User types `/commandname args` in prompt
2. UI detects "/" prefix and parses command
3. `SessionPrompt.command()` processes the command
4. Template placeholders (`$1`, `$2`, `$ARGUMENTS`) are substituted
5. Command publishes `Command.Event.Executed` event
6. Prompt is sent to model

**Command Sources:**
- Built-in: `init`, `review`
- User-defined: `config.command` section in opencode.jsonc
- MCP Prompts: Loaded from connected MCP servers

### Event Available

```typescript
// Defined in command/index.ts:12-20
export const Event = {
  Executed: BusEvent.define(
    "command.executed",
    z.object({
      name: z.string(),           // Command name
      sessionID: z.string(),      // Session ID
      arguments: z.string(),      // User arguments
      messageID: z.string(),      // Message ID
    }),
  ),
}

// Published in session/prompt.ts:1586-1591
Bus.publish(Command.Event.Executed, {
  name: input.command,
  sessionID: input.sessionID,
  arguments: input.arguments,
  messageID: result.info.id,
})
```

### How to Capture in Plugin

```typescript
event: async (input) => {
  const event = input.event as any

  if (event.type === "command.executed") {
    const { name, sessionID, arguments: args, messageID } = event.properties

    // Record metrics
    Metrics.recordCommandExecution({
      command: name,
      sessionID,
      hasArguments: args.length > 0,
      argumentCount: args.split(/\s+/).filter(Boolean).length,
    })

    Logger.log(`COMMAND EXECUTED: /${name} (args="${args}", session=${sessionID.slice(0,12)}...)`)
  }
}
```

### Data Available

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Command identifier (e.g., "init", "review", custom) |
| `sessionID` | string | Session context where command was run |
| `arguments` | string | User-provided arguments after command name |
| `messageID` | string | Associated message ID |

### Additional Data (via Command.get())

You can also access command metadata by calling `Command.get(name)`:

| Field | Type | Description |
|-------|------|-------------|
| `description` | string | Human-readable description |
| `agent` | string | Optional agent override |
| `model` | string | Optional model override |
| `mcp` | boolean | Whether from MCP prompt |
| `subtask` | boolean | Whether runs as subtask |
| `hints` | string[] | Placeholder hints ($1, $2, etc.) |

---

## 2. Skills (Agent Skills)

### How It Works in OpenCode

**Source Files:**
- Discovery: `/home/mtk26468/opencode/packages/opencode/src/skill/skill.ts`
- Tool: `/home/mtk26468/opencode/packages/opencode/src/tool/skill.ts`

**Flow:**
1. Skills discovered by scanning for `SKILL.md` files in:
   - `.opencode/skill/**`
   - `.claude/skills/**`
   - `~/.claude/skills/**`
2. Skills exposed as a tool named `skill`
3. Agent calls `skill` tool with skill name parameter
4. Permission check via `ctx.ask({ permission: "skill", ... })`
5. SKILL.md content loaded and returned to agent

**Skill Definition (SKILL.md):**
```markdown
---
name: code-review
description: Review code changes for quality
---

Your skill instructions here...
```

### Events Available

Skills are captured via **tool execution hooks** since skills are exposed as a tool:

```typescript
// In tool/skill.ts - execute returns:
return {
  title: `Loaded skill: ${skill.name}`,
  output: skillContent,
  metadata: {
    name: skill.name,    // Skill identifier
    dir: baseDirectory,  // Skill's base directory
  },
}
```

Permission events are also published:
```typescript
// permission.asked event with:
{
  permission: "skill",
  patterns: [skillName],
  ...
}
```

### How to Capture in Plugin

```typescript
// Track skill invocations
const skillInvocations = new Map<string, { startTime: number; skillName?: string }>()

"tool.execute.before": async (input, output) => {
  if (input.tool === "skill") {
    const skillName = output.args?.name
    skillInvocations.set(input.callID, {
      startTime: Date.now(),
      skillName,
    })
    Logger.log(`SKILL INVOKED: ${skillName} (callID=${input.callID})`)
  }
},

"tool.execute.after": async (input, output) => {
  if (input.tool === "skill") {
    const invocation = skillInvocations.get(input.callID)
    const duration = invocation ? Date.now() - invocation.startTime : 0

    const { name, dir } = output.metadata || {}

    Metrics.recordSkillInvocation({
      skill: name || invocation?.skillName || "unknown",
      directory: dir,
      duration,
      sessionID: input.sessionID,
      status: "success",
    })

    Logger.log(`SKILL LOADED: ${name} from ${dir} (duration=${duration}ms)`)
    skillInvocations.delete(input.callID)
  }
}
```

### Data Available

| Field | Source | Description |
|-------|--------|-------------|
| `name` | output.metadata | Skill identifier |
| `dir` | output.metadata | Skill's base directory |
| `sessionID` | input | Session context |
| `callID` | input | Unique call identifier |
| `duration` | calculated | Time to load skill (ms) |
| `args.name` | output.args | Requested skill name |

---

## 3. MCP (Model Context Protocol)

### How It Works in OpenCode

**Source Files:**
- Core: `/home/mtk26468/opencode/packages/opencode/src/mcp/index.ts`
- OAuth: `/home/mtk26468/opencode/packages/opencode/src/mcp/oauth-provider.ts`
- Tool Integration: `/home/mtk26468/opencode/packages/opencode/src/session/prompt.ts` (lines 641-817)

**MCP Server Types:**
1. **Local (stdio):** Spawned subprocess, configured with `{ type: "local", command: [...] }`
2. **Remote (HTTP):** HTTP endpoint with optional OAuth, configured with `{ type: "remote", url: "..." }`

**Flow:**
1. MCP servers configured in opencode.jsonc under `mcp` section
2. Servers connected on first access (lazy initialization)
3. Tools from all servers merged into tool registry
4. Tool names sanitized to: `{clientName}_{toolName}` (alphanumeric + underscore/hyphen)
5. Tool calls go through standard `tool.execute.before/after` hooks
6. MCP transport handles serialization/communication

**Tool Naming Convention:**
```typescript
// Example: MCP server "filesystem" with tool "read_file"
// Becomes tool name: "filesystem_read_file"
const sanitizedName = `${clientName}_${toolName}`.replace(/[^a-zA-Z0-9_-]/g, "_")
```

### Events Available

**MCP Tools Changed Event:**
```typescript
// Defined in mcp/index.ts:42-47
export const ToolsChanged = BusEvent.define(
  "mcp.tools.changed",
  z.object({
    server: z.string(),
  }),
)

// Published when server notifies of tool list change
Bus.publish(ToolsChanged, { server: serverName })
```

**Tool Execution (via standard hooks):**
- MCP tools captured in `tool.execute.before/after` with tool name format `server_tool`

### How to Capture in Plugin

```typescript
// Detect MCP tools by naming pattern
function isMCPTool(toolName: string): { isMCP: boolean; server?: string; tool?: string } {
  // MCP tools follow pattern: serverName_toolName
  // Built-in tools are single words: read, write, edit, bash, glob, grep, etc.
  const parts = toolName.split("_")
  if (parts.length >= 2) {
    // Could be MCP tool - check against known built-in patterns
    const builtInTools = [
      "read", "write", "edit", "bash", "glob", "grep", "task", "skill",
      "mcp", "lsp", "web_fetch", "web_search", "notebook_edit", "ask_user"
    ]
    if (!builtInTools.includes(toolName)) {
      return {
        isMCP: true,
        server: parts[0],
        tool: parts.slice(1).join("_"),
      }
    }
  }
  return { isMCP: false }
}

// Track MCP tool invocations
const mcpInvocations = new Map<string, { startTime: number; server: string; tool: string }>()

"tool.execute.before": async (input, output) => {
  const mcpInfo = isMCPTool(input.tool)
  if (mcpInfo.isMCP) {
    mcpInvocations.set(input.callID, {
      startTime: Date.now(),
      server: mcpInfo.server!,
      tool: mcpInfo.tool!,
    })
    Logger.log(`MCP TOOL INVOKED: ${mcpInfo.server}/${mcpInfo.tool} (callID=${input.callID})`)
  }
},

"tool.execute.after": async (input, output) => {
  const invocation = mcpInvocations.get(input.callID)
  if (invocation) {
    const duration = Date.now() - invocation.startTime
    const status = output.error ? "error" : "success"

    Metrics.recordMCPToolExecution({
      server: invocation.server,
      tool: invocation.tool,
      duration,
      status,
      sessionID: input.sessionID,
    })

    Logger.log(`MCP TOOL COMPLETED: ${invocation.server}/${invocation.tool} (status=${status}, duration=${duration}ms)`)
    mcpInvocations.delete(input.callID)
  }
},

event: async (input) => {
  const event = input.event as any

  if (event.type === "mcp.tools.changed") {
    const { server } = event.properties
    Metrics.recordMCPToolsRefresh({ server })
    Logger.log(`MCP TOOLS CHANGED: server=${server}`)
  }
}
```

### Data Available

| Field | Source | Description |
|-------|--------|-------------|
| `tool` | input.tool | Full tool name (server_tool) |
| `server` | parsed from tool name | MCP server/client name |
| `mcpTool` | parsed from tool name | Tool name within server |
| `sessionID` | input | Session context |
| `callID` | input | Unique call identifier |
| `duration` | calculated | Execution time (ms) |
| `status` | output | success/error |
| `args` | output.args | Tool arguments |
| `error` | output.error | Error message if failed |

### MCP Server Configuration Access

For more detailed server info, you could potentially access the MCP module's status:

```typescript
// These are internal APIs (not exposed via plugin SDK currently)
// But the event system provides enough for observability

// Available via mcp.tools.changed event:
// - Which server had tools change

// Available via tool execution:
// - Server name (from tool name)
// - Tool name
// - Execution metrics
```

---

## 4. Agents (Task/Subagents)

### How It Works in OpenCode

**Source Files:**
- Agent Definitions: `/home/mtk26468/opencode/packages/opencode/src/agent/agent.ts`
- Task Tool: `/home/mtk26468/opencode/packages/opencode/src/tool/task.ts`
- Prompt Processing: `/home/mtk26468/opencode/packages/opencode/src/session/prompt.ts`

**Built-in Agents:**

| Agent | Mode | Description |
|-------|------|-------------|
| `build` | primary | Primary agent for building |
| `plan` | primary | Primary agent for planning |
| `general` | subagent | General-purpose multi-step tasks |
| `explore` | subagent | Fast codebase exploration |
| `compaction` | hidden | Session compaction |
| `title` | hidden | Generate session titles |
| `summary` | hidden | Summarize sessions |

Custom agents can be defined in config.

**Flow:**
1. Agent calls `task` tool with agent type, description, prompt
2. Permission check via `ctx.ask({ permission: "task", ... })`
3. New child session created with parent reference
4. Subagent executes in child session
5. Parent subscribes to `MessageV2.Event.PartUpdated` for progress
6. Task tool returns summary when subagent completes

**Session Hierarchy:**
```
Parent Session (user conversation)
  └── Child Session (subagent task)
        ├── Tool calls tracked
        └── Final result returned to parent
```

### Events Available

**Session Created:**
```typescript
// Defined in session/index.ts
Session.Event.Created = BusEvent.define("session.created", z.object({
  id: z.string(),
  parentID: z.string().optional(),  // Present for subagent sessions
  title: z.string(),
  // ... other fields
}))
```

**Message Part Updated:**
```typescript
// Defined in session/message-v2.ts
MessageV2.Event.PartUpdated = BusEvent.define("message.part.updated", z.object({
  part: z.object({
    sessionID: z.string(),
    messageID: z.string(),
    type: z.string(),
    tool: z.string().optional(),
    state: z.object({
      status: z.enum(["pending", "running", "completed", "error"]),
      // ...
    }),
  }),
}))
```

**Permission Asked:**
```typescript
// permission.asked event with:
{
  permission: "task",
  patterns: [agentType],
  metadata: {
    description: taskDescription,
    subagent_type: agentType,
  }
}
```

### How to Capture in Plugin

```typescript
// Track agent invocations
interface AgentInvocation {
  startTime: number
  agentType: string
  description: string
  childSessionID?: string
  toolCount: number
}
const agentInvocations = new Map<string, AgentInvocation>()

// Track child sessions to agent invocations
const sessionToAgent = new Map<string, string>()  // childSessionID -> callID

"tool.execute.before": async (input, output) => {
  if (input.tool === "task") {
    const { subagent_type, description, prompt } = output.args || {}

    agentInvocations.set(input.callID, {
      startTime: Date.now(),
      agentType: subagent_type || "unknown",
      description: description || "",
      toolCount: 0,
    })

    Logger.log(`AGENT SPAWNED: @${subagent_type} - "${description}" (callID=${input.callID})`)
  }
},

"tool.execute.after": async (input, output) => {
  if (input.tool === "task") {
    const invocation = agentInvocations.get(input.callID)
    if (invocation) {
      const duration = Date.now() - invocation.startTime
      const { sessionId, summary } = output.metadata || {}

      // Count tools used by agent
      const toolCount = Array.isArray(summary) ? summary.length : 0

      Metrics.recordAgentExecution({
        agentType: invocation.agentType,
        description: invocation.description,
        duration,
        toolCount,
        childSessionID: sessionId,
        parentSessionID: input.sessionID,
        status: "completed",
      })

      Logger.log(`AGENT COMPLETED: @${invocation.agentType} (duration=${duration}ms, tools=${toolCount})`)

      // Cleanup
      if (sessionId) sessionToAgent.delete(sessionId)
      agentInvocations.delete(input.callID)
    }
  }
},

event: async (input) => {
  const event = input.event as any

  // Track child session creation
  if (event.type === "session.created") {
    const { id, parentID, title } = event.properties
    if (parentID) {
      // This is a subagent session
      // Try to correlate with agent invocation
      Logger.log(`SUBAGENT SESSION CREATED: id=${id}, parent=${parentID}, title="${title}"`)
    }
  }

  // Track tool usage in subagent sessions
  if (event.type === "message.part.updated") {
    const { part } = event.properties
    if (part.type === "tool" && sessionToAgent.has(part.sessionID)) {
      const callID = sessionToAgent.get(part.sessionID)!
      const invocation = agentInvocations.get(callID)
      if (invocation && part.state.status === "completed") {
        invocation.toolCount++
      }
    }
  }
}
```

### Data Available

| Field | Source | Description |
|-------|--------|-------------|
| `subagent_type` | output.args | Agent name (general, explore, plan) |
| `description` | output.args | Task description (3-5 words) |
| `prompt` | output.args | Full prompt given to agent |
| `session_id` | output.args | Optional existing session to continue |
| `sessionId` | output.metadata | Child session ID (created) |
| `summary` | output.metadata | Array of tool execution summaries |
| `callID` | input | Unique call identifier |
| `sessionID` | input | Parent session ID |
| `duration` | calculated | Total agent execution time (ms) |
| `toolCount` | calculated | Number of tools used by agent |

### Agent Tool Summary Structure

The `summary` in metadata contains:
```typescript
interface ToolSummary {
  id: string           // Part ID
  tool: string         // Tool name
  state: {
    status: string     // "completed" | "error"
    title?: string     // Completion title
  }
}
```

---

## Implementation Details

### Recommended Approach

Extend your existing plugin with new handlers:

```typescript
// src/index.ts - additions

import * as FeatureMetrics from "./feature-metrics.js"

const plugin: Plugin = async (input) => {
  return {
    config: async (config) => {
      // ... existing config handling
      await FeatureMetrics.initialize()
    },

    "tool.execute.before": async (input, output) => {
      // ... existing LOC handling

      // Add feature tracking
      FeatureMetrics.trackToolBefore(input, output)
    },

    "tool.execute.after": async (input, output) => {
      // ... existing LOC handling

      // Add feature tracking
      FeatureMetrics.trackToolAfter(input, output)
    },

    event: async (input) => {
      // ... existing permission handling

      // Add feature tracking
      FeatureMetrics.trackEvent(input.event)
    },
  }
}
```

### New File: src/feature-metrics.ts

```typescript
import { Counter, Histogram } from "@opentelemetry/api"

// Metrics instruments
let commandCounter: Counter
let skillCounter: Counter
let skillDuration: Histogram
let mcpToolCounter: Counter
let mcpToolDuration: Histogram
let agentCounter: Counter
let agentDuration: Histogram
let agentToolCount: Histogram

// Tracking state
const skillInvocations = new Map<string, { startTime: number; name?: string }>()
const mcpInvocations = new Map<string, { startTime: number; server: string; tool: string }>()
const agentInvocations = new Map<string, { startTime: number; type: string; desc: string }>()

export async function initialize() {
  // Create metric instruments
  // ... meter.createCounter(), meter.createHistogram()
}

export function trackToolBefore(input: any, output: any) {
  if (input.tool === "skill") {
    skillInvocations.set(input.callID, {
      startTime: Date.now(),
      name: output.args?.name,
    })
  }

  const mcpInfo = detectMCPTool(input.tool)
  if (mcpInfo.isMCP) {
    mcpInvocations.set(input.callID, {
      startTime: Date.now(),
      server: mcpInfo.server,
      tool: mcpInfo.tool,
    })
  }

  if (input.tool === "task") {
    agentInvocations.set(input.callID, {
      startTime: Date.now(),
      type: output.args?.subagent_type || "unknown",
      desc: output.args?.description || "",
    })
  }
}

export function trackToolAfter(input: any, output: any) {
  // Handle skill
  const skillInv = skillInvocations.get(input.callID)
  if (skillInv) {
    const duration = Date.now() - skillInv.startTime
    skillCounter.add(1, { skill: output.metadata?.name || skillInv.name })
    skillDuration.record(duration, { skill: output.metadata?.name || skillInv.name })
    skillInvocations.delete(input.callID)
  }

  // Handle MCP
  const mcpInv = mcpInvocations.get(input.callID)
  if (mcpInv) {
    const duration = Date.now() - mcpInv.startTime
    mcpToolCounter.add(1, { server: mcpInv.server, tool: mcpInv.tool })
    mcpToolDuration.record(duration, { server: mcpInv.server, tool: mcpInv.tool })
    mcpInvocations.delete(input.callID)
  }

  // Handle Agent
  const agentInv = agentInvocations.get(input.callID)
  if (agentInv) {
    const duration = Date.now() - agentInv.startTime
    const toolCount = output.metadata?.summary?.length || 0
    agentCounter.add(1, { agent: agentInv.type })
    agentDuration.record(duration, { agent: agentInv.type })
    agentToolCount.record(toolCount, { agent: agentInv.type })
    agentInvocations.delete(input.callID)
  }
}

export function trackEvent(event: any) {
  if (event.type === "command.executed") {
    commandCounter.add(1, { command: event.properties.name })
  }
}
```

---

## Proposed Metrics

### Counter Metrics

| Metric Name | Labels | Description |
|-------------|--------|-------------|
| `opencode.command.executions` | command, sessionID | Slash command usage |
| `opencode.skill.invocations` | skill, sessionID | Skill loading |
| `opencode.mcp.tool.executions` | server, tool, status, sessionID | MCP tool calls |
| `opencode.mcp.tools.refreshed` | server | MCP server tool list updates |
| `opencode.agent.spawns` | agent_type, sessionID | Agent invocations |

### Histogram Metrics

| Metric Name | Labels | Unit | Description |
|-------------|--------|------|-------------|
| `opencode.skill.duration` | skill | ms | Time to load skill |
| `opencode.mcp.tool.duration` | server, tool | ms | MCP tool execution time |
| `opencode.agent.duration` | agent_type | ms | Total agent execution time |
| `opencode.agent.tool_count` | agent_type | count | Tools used per agent invocation |

### JSON Export Format (Optional)

```json
{
  "timestamp": "2026-02-05T10:30:00Z",
  "type": "command_execution",
  "data": {
    "command": "review",
    "arguments": "main",
    "sessionID": "session_abc123",
    "user": "mtk26468",
    "model": "claude-sonnet-4"
  }
}

{
  "timestamp": "2026-02-05T10:31:00Z",
  "type": "agent_execution",
  "data": {
    "agent_type": "explore",
    "description": "Find auth implementations",
    "duration_ms": 5420,
    "tool_count": 8,
    "parent_session": "session_abc123",
    "child_session": "session_def456"
  }
}
```

---

## Key Files Reference

### OpenCode Source Files

| File | Purpose |
|------|---------|
| `packages/opencode/src/command/index.ts` | Command definitions, `Command.Event.Executed` |
| `packages/opencode/src/skill/skill.ts` | Skill discovery from SKILL.md files |
| `packages/opencode/src/tool/skill.ts` | Skill tool implementation |
| `packages/opencode/src/mcp/index.ts` | MCP server/tool management, `MCP.ToolsChanged` |
| `packages/opencode/src/tool/task.ts` | Agent spawn via task tool |
| `packages/opencode/src/agent/agent.ts` | Agent definitions and registry |
| `packages/opencode/src/session/prompt.ts` | Command/prompt execution, tool resolution |
| `packages/opencode/src/session/processor.ts` | Tool state management |
| `packages/opencode/src/bus/index.ts` | Event bus system |
| `packages/opencode/src/bus/bus-event.ts` | Event type definitions |
| `packages/opencode/src/plugin/index.ts` | Plugin loading and hook system |

### Your Plugin Files

| File | Purpose |
|------|---------|
| `src/index.ts` | Main plugin, hooks registration |
| `src/metrics.ts` | OpenTelemetry metrics |
| `src/traces.ts` | OpenTelemetry traces |
| `src/correlation.ts` | Request correlation tracking |

---

## Limitations and Considerations

### What's Captured

- All slash command executions (built-in and custom)
- All skill invocations via the `skill` tool
- All MCP tool calls (identifiable by naming pattern)
- All agent spawns via the `task` tool
- Parent/child session relationships

### What's NOT Directly Captured (but could be inferred)

1. **MCP Server Connection Status** - Not exposed via events, but tool failures indicate issues
2. **Skill Discovery** - When skills are scanned, not when invoked
3. **Agent Internal Reasoning** - Model thinking/reasoning not accessible
4. **Cancelled Operations** - Partial data if user cancels

### Edge Cases

1. **Custom Tool Names with Underscores** - Could be misidentified as MCP tools
   - Mitigation: Maintain list of known built-in tools

2. **Nested Agent Calls** - Agents can spawn other agents
   - Solution: Track session hierarchy via parentID

3. **Long-Running Agents** - May timeout or be cancelled
   - Solution: Track status in `tool.execute.after` output

---

## Conclusion

**All four features are fully observable** through the existing plugin hook system:

1. **No OpenCode source modifications required** - use existing hooks
2. **Your current plugin architecture works** - just add more handlers
3. **Rich data available** - command names, skill names, MCP servers/tools, agent types
4. **Parent/child session tracking** for agent hierarchies
5. **Timing data** for performance analysis

The opencode plugin architecture is well-designed for extensibility. Your telemetry plugin can be extended to capture comprehensive observability data for all these features with the implementation patterns shown above.

---

## Next Steps

1. Add feature metrics module to existing plugin
2. Implement MCP tool detection logic
3. Add command execution tracking
4. Implement agent tracking with session correlation
5. Update OTLP export configuration for new metrics
6. Test with real opencode sessions
