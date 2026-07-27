import type { Plugin } from "@opencode-ai/plugin"

// 匹配 @" "@ (可扩展 here-string) 中的反引号 `
// PowerShell 中 @" "@ 会解释反引号转义序列，容易导致意外行为
// 应使用 @' '@ (字面 here-string) 来避免转义
const hereStringBacktickRe = /@"[\s\S]*?`[\s\S]*?"@/

export default (async () => {
  return {
    "tool.execute.before": async (input, output) => {
      const tool = String(input?.tool ?? "").toLowerCase()
      if (tool !== "bash" && tool !== "shell") return

      const args = output?.args
      if (!args || typeof args !== "object") return

      const command = (args as Record<string, unknown>).command
      if (typeof command !== "string" || !command) return

      if (hereStringBacktickRe.test(command)) {
        throw new Error(
          "[no-backtick-herestring] 命令在 @\" \"@ here-string 中使用了反引号 `。\n" +
          "PowerShell 的 @\" \"@ (可扩展 here-string) 会解释反引号转义序列，容易导致意外行为。\n" +
          "请改用 @' '@ (字面 here-string)，其中的内容会保持原样，不会被解释。"
        )
      }
    },
  }
}) satisfies Plugin
