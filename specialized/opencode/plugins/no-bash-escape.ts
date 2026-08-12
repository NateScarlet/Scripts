import type { Plugin } from "@opencode-ai/plugin"

// 匹配 bash 风格转义序列
// 排除 Windows 盘符（C:\）及前邻字母的 \n \t \r 以减少路径误报
// 注意：pwsh 使用反引号 ` 转义，不是反斜杠，因此不拦截反引号
// 捕获场景：\$ \" \` \\n \\t \\r \xHH \uHHHH
const bashEscapeRe = /(?:(?<![A-Za-z]:)(?<![A-Za-z])\\(?:[$"`ntr]|x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}))/g

export default (async () => {
  return {
    "tool.execute.before": async (input, output) => {
      const tool = String(input?.tool ?? "").toLowerCase()
      if (tool !== "bash" && tool !== "shell") return

      const args = output?.args
      if (!args || typeof args !== "object") return

      const command = (args as Record<string, unknown>).command
      if (typeof command !== "string" || !command) return

      const hits = [...command.matchAll(bashEscapeRe)]
      if (hits.length === 0) return

      const details = hits
        .map((hit) => {
          const at = hit.index ?? 0
          const seq = hit[0]
          const start = Math.max(0, at - 10)
          const end = Math.min(command.length, at + seq.length + 10)
          const prefix = start > 0 ? "…" : ""
          const suffix = end < command.length ? "…" : ""
          return `  第 ${at + 1} 个字符处：${JSON.stringify(seq)}（上下文：${prefix}${command.slice(start, end)}${suffix}）`
        })
        .join("\n")

      throw new Error(
        "[no-bash-escape] 命令包含 bash 风格的转义序列，但本机使用 pwsh（使用反引号 ` 转义）：\n" +
          details +
          "\n" +
          "如需使用 bash 转义，请将内容写入项目 .scratch/ 目录的文件中，再通过读取文件变量或工具的文件参数传入。\n" +
          "路径请使用正斜杠（如 ./temp/file）而非反斜杠，以避免与转义序列混淆。"
      )
    },
  }
}) satisfies Plugin
