import * as fs from "fs"
import * as path from "path"
import * as os from "os"

/**
 * Simple file-based logger for the plugin
 * Writes to ~/.local/share/opencode/telemetry-plugin.log
 */

const LOG_DIR = path.join(os.homedir(), ".local", "share", "opencode")
const LOG_FILE = path.join(LOG_DIR, "telemetry-plugin.log")
const MAX_LOG_SIZE = 10 * 1024 * 1024 // 10MB
let logStream: fs.WriteStream | null = null

/**
 * Initialize the logger
 */
export function initLogger(): void {
  try {
    // Create directory if it doesn't exist
    if (!fs.existsSync(LOG_DIR)) {
      fs.mkdirSync(LOG_DIR, { recursive: true })
    }

    // Check if log file is too large and rotate it
    if (fs.existsSync(LOG_FILE)) {
      const stats = fs.statSync(LOG_FILE)
      if (stats.size > MAX_LOG_SIZE) {
        const backupFile = LOG_FILE + ".old"
        if (fs.existsSync(backupFile)) {
          fs.unlinkSync(backupFile)
        }
        fs.renameSync(LOG_FILE, backupFile)
      }
    }

    // Create write stream (append mode)
    logStream = fs.createWriteStream(LOG_FILE, { flags: "a" })

    log("Logger initialized")
  } catch (error) {
    console.error("[opencode-telemetry] Failed to initialize logger:", error)
  }
}

/**
 * Log a message to the file
 */
export function log(message: string, data?: any): void {
  try {
    const timestamp = new Date().toISOString()
    let logMessage = `[${timestamp}] ${message}`

    if (data !== undefined) {
      if (typeof data === "object") {
        logMessage += ` ${JSON.stringify(data)}`
      } else {
        logMessage += ` ${data}`
      }
    }

    logMessage += "\n"

    if (logStream) {
      logStream.write(logMessage)
    } else {
      // Fallback to sync write if stream not initialized
      fs.appendFileSync(LOG_FILE, logMessage)
    }
  } catch (error) {
    // Silent fail to not disrupt OpenCode
    console.error("[opencode-telemetry] Failed to write log:", error)
  }
}

/**
 * Log an error
 */
export function error(message: string, err?: any): void {
  log(`ERROR: ${message}`, err)
}

/**
 * Log a debug message
 */
export function debug(message: string, data?: any): void {
  log(`DEBUG: ${message}`, data)
}

/**
 * Close the logger
 */
export function closeLogger(): void {
  if (logStream) {
    logStream.end()
    logStream = null
  }
}

/**
 * Get the log file path
 */
export function getLogFilePath(): string {
  return LOG_FILE
}
