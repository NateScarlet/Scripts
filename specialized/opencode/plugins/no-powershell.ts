import type { Plugin } from "@opencode-ai/plugin"

// 匹配 powershell.exe / powershell 作为独立命令调用（不匹配 pwsh）
const re = /\bpowershell(?:\.exe)?(?:\s|$|["'])/i

export default (async () => {
  return {
    "tool.execute.before": async (input, output) => {
      const tool = String(input?.tool ?? "").toLowerCase()
      if (tool !== "bash" && tool !== "shell") return

      const args = output?.args
      if (!args || typeof args !== "object") return

      const command = (args as Record<string, unknown>).command
      if (typeof command !== "string" || !command) return

      if (re.test(command)) {
        throw new Error("[no-powershell] 请使用 pwsh 而非 Windows PowerShell")
      }
    },
  }
}) satisfies Plugin
