# OpenCode Config Schema Investigation

## Question

Can OpenCode plugins receive custom configuration fields through the `opencode.jsonc` config file, or does OpenCode's config schema only support predefined fields?

## Answer: **Config Schema is STRICT - Custom Fields Are NOT Supported** ❌

### Evidence

#### 1. Zod Schema Uses `.strict()` Mode

**File:** `/home/mtk26468/opencode/packages/opencode/src/config/config.ts:1047`

```typescript
.strict()
.meta({
  ref: "Config",
})
```

The Zod schema validation uses `.strict()` mode, which **rejects any fields not explicitly defined** in the schema.

#### 2. Experimental Schema Definition

**File:** `/home/mtk26468/opencode/packages/opencode/src/config/config.ts:1002-1044`

```typescript
experimental: z
  .object({
    hook: z.object({...}).optional(),
    chatMaxRetries: z.number().optional(),
    disable_paste_summary: z.boolean().optional(),
    batch_tool: z.boolean().optional(),
    openTelemetry: z.boolean().optional(),
    primary_tools: z.array(z.string()).optional(),
    continue_loop_on_deny: z.boolean().optional(),
    mcp_timeout: z.number().int().positive().optional(),
  })
  .optional(),
```

The `experimental` object schema **only** includes these fields:
- ✅ `hook`
- ✅ `chatMaxRetries`
- ✅ `disable_paste_summary`
- ✅ `batch_tool`
- ✅ `openTelemetry`
- ✅ `primary_tools`
- ✅ `continue_loop_on_deny`
- ✅ `mcp_timeout`

**NOT INCLUDED:**
- ❌ `telemetry` (our custom field)

#### 3. SDK Config Type Definition

**File:** `/home/mtk26468/opencode/packages/sdk/js/src/gen/types.gen.ts`

```typescript
experimental?: {
  hook?: {...}
  chatMaxRetries?: number
  disable_paste_summary?: boolean
  batch_tool?: boolean
  openTelemetry?: boolean
  primary_tools?: Array<string>
}
```

The generated TypeScript types confirm that `telemetry` is **not part of the official schema**.

#### 4. Plugin Config Hook

**File:** `/home/mtk26468/opencode/packages/plugin/src/index.ts:150`

```typescript
export interface Hooks {
  config?: (input: Config) => Promise<void>
  // ...
}
```

The plugin's `config` hook receives a `Config` type from `@opencode-ai/sdk`, which has already been:
1. Parsed by Zod
2. Validated against the strict schema
3. **Cleaned of unknown fields**

## What Happens to Custom Fields?

When you add a custom field like `telemetry` to your config:

```jsonc
{
  "experimental": {
    "openTelemetry": true,
    "telemetry": {  // ← CUSTOM FIELD
      "endpoint": "http://localhost:4318",
      "protocol": "http"
    }
  }
}
```

**The config loading process:**

1. OpenCode reads the config file
2. Zod parses it with `.strict()` mode
3. Zod **STRIPS OUT** the `telemetry` field because it's not in the schema
4. Plugin receives the cleaned config (without `telemetry`)

**Result:**
```typescript
// What the plugin actually receives:
{
  experimental: {
    openTelemetry: true
    // telemetry field is GONE!
  }
}
```

## Why Our Config Didn't Work

Looking at our plugin logs:

```
[2026-01-26T08:56:10.061Z] DEBUG: experimental object {
  "openTelemetry": true
}
```

The `telemetry` section we added was **stripped out** by the Zod schema validation before it reached our plugin!

## Solution: Use Environment Variables

Since custom config fields are not supported, we must use **environment variables** which bypass the config schema:

### Option 1: Set Environment Variables

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"
export OTEL_EXPORTER_OTLP_PROTOCOL="http"
```

### Option 2: Update Config Parser to Use Only Env Vars

Our config parser already supports environment variables:

```typescript
// src/config.ts
const endpoint =
  userConfig?.endpoint ||  // ← This will always be undefined (stripped by schema)
  process.env.OTEL_EXPORTER_OTLP_ENDPOINT ||  // ← Use this instead!
  "http://localhost:4318"
```

## Alternative: Request Schema Change from OpenCode Team

To properly support custom telemetry configuration, we would need to:

1. **Submit PR to OpenCode core** to add `telemetry` to the schema:

```typescript
// In /home/mtk26468/opencode/packages/opencode/src/config/config.ts
experimental: z
  .object({
    // ... existing fields ...
    openTelemetry: z.boolean().optional(),
    telemetry: z.object({  // ← ADD THIS
      endpoint: z.string().optional(),
      protocol: z.enum(["grpc", "http"]).optional(),
      exportIntervalMillis: z.number().optional(),
      headers: z.record(z.string(), z.string()).optional(),
    }).optional(),
  })
  .optional(),
```

2. **Update SDK types** to include the new field
3. **Wait for OpenCode release** with the change

## Recommended Approach

For now, the **pragmatic solution** is:

1. **Remove custom `telemetry` section** from config files (it doesn't work)
2. **Keep `experimental.openTelemetry: true`** (this works - it's in the schema)
3. **Use environment variables** for endpoint configuration
4. **Update documentation** to reflect this limitation

### Updated Config (Working)

```jsonc
{
  "experimental": {
    "openTelemetry": true
    // Don't add telemetry here - it won't work!
  }
}
```

### Set via Environment Variables

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"
export OTEL_EXPORTER_OTLP_PROTOCOL="http"
opencode
```

## Conclusion

**Answer to your question:**

> Do you think if this is due to the config hook implementation in opencode core only support their defined config?

**YES, EXACTLY.** OpenCode's config system uses Zod with `.strict()` mode, which:
- ✅ Only accepts predefined fields in the schema
- ❌ Rejects/strips custom fields like our `telemetry` object
- ❌ Cannot be extended by plugins without modifying OpenCode core

**Our custom `telemetry` config field is being silently discarded** during config parsing, which is why the plugin always sees an empty `experimental` object (except for `openTelemetry: true`).

**The only way to pass configuration to our plugin is:**
1. Environment variables (bypass config schema)
2. Propose changes to OpenCode core schema (long-term solution)
