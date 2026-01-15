/**
 * Map of file extensions to programming languages
 */
export const LANGUAGE_MAP: Record<string, string> = {
  // Web Technologies
  ts: "typescript",
  tsx: "typescript",
  js: "javascript",
  jsx: "javascript",
  mjs: "javascript",
  cjs: "javascript",
  html: "html",
  htm: "html",
  css: "css",
  scss: "scss",
  sass: "sass",
  less: "less",
  vue: "vue",
  svelte: "svelte",

  // Systems Programming
  rs: "rust",
  go: "go",
  cpp: "cpp",
  cc: "cpp",
  cxx: "cpp",
  c: "c",
  h: "c_header",
  hpp: "cpp_header",
  hh: "cpp_header",
  hxx: "cpp_header",

  // Scripting Languages
  py: "python",
  pyw: "python",
  rb: "ruby",
  php: "php",
  sh: "shell",
  bash: "shell",
  zsh: "shell",
  fish: "shell",
  ps1: "powershell",
  lua: "lua",
  pl: "perl",

  // JVM Languages
  java: "java",
  kt: "kotlin",
  kts: "kotlin",
  scala: "scala",
  groovy: "groovy",
  clj: "clojure",

  // .NET Languages
  cs: "csharp",
  fs: "fsharp",
  vb: "vb",

  // Mobile
  swift: "swift",
  m: "objective-c",
  mm: "objective-cpp",
  dart: "dart",

  // Data & Config
  json: "json",
  jsonc: "json",
  yaml: "yaml",
  yml: "yaml",
  toml: "toml",
  xml: "xml",
  ini: "ini",
  conf: "config",
  properties: "properties",

  // Markup & Documentation
  md: "markdown",
  mdx: "markdown",
  rst: "restructuredtext",
  tex: "latex",
  adoc: "asciidoc",

  // Databases
  sql: "sql",
  psql: "sql",
  mysql: "sql",
  pgsql: "sql",

  // Other
  r: "r",
  jl: "julia",
  ex: "elixir",
  exs: "elixir",
  erl: "erlang",
  hrl: "erlang",
  zig: "zig",
  nim: "nim",
  v: "v",
  vhd: "vhdl",
  vhdl: "vhdl",
}

/**
 * Infer programming language from a file path
 * @param filepath - Path to the file
 * @returns Language name or "unknown"
 */
export function inferLanguage(filepath: string): string {
  const ext = filepath.split(".").pop()?.toLowerCase()
  if (!ext) return "unknown"
  return LANGUAGE_MAP[ext] || "unknown"
}

/**
 * Infer language from multiple files
 * Returns "mixed" if multiple different languages detected
 * @param files - Array of file paths
 * @returns Language name, "mixed", or "unknown"
 */
export function inferLanguageFromMultiple(files: string[]): string {
  if (files.length === 0) return "unknown"
  if (files.length === 1) return inferLanguage(files[0])

  const languages = new Set(files.map(inferLanguage).filter((lang) => lang !== "unknown"))

  if (languages.size === 0) return "unknown"
  if (languages.size === 1) return Array.from(languages)[0]
  return "mixed"
}
