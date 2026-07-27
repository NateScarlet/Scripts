import type { Plugin } from "@opencode-ai/plugin"

// 匹配 bash 风格转义序列
// 排除 Windows 盘符（C:\）及前邻字母的 \n \t \r 以减少路径误报
// 注意：pwsh 使用反引号 ` 转义，不是反斜杠，因此不拦截反引号
// 捕获场景：\$ \" \` \\n \\t \\r \xHH \uHHHH
const bashEscapeRe = /(?:(?<![A-Za-z]:)(?<![A-Za-z])\\(?:[$"`ntr]|x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}))/

export default (async () => {
  return {
    "tool.execute.before": async (input, output) => {
      const tool = String(input?.tool ?? "").toLowerCase()
      if (tool !== "bash" && tool !== "shell") return

      const args = output?.args
      if (!args || typeof args !== "object") return

      const command = (args as Record<string, unknown>).command
      if (typeof command !== "string" || !command) return

      if (bashEscapeRe.test(command)) {
        throw new Error(
          "[no-bash-escape] 命令包含 bash 风格的转义序列（\\$ \\\" \\` \\n \\t 等），但本机使用 pwsh（使用反引号 ` 转义）。\n" +
          "如需使用 bash 转义，请将内容写入项目 .scratch/ 目录的文件中，再通过读取文件变量或工具的文件参数传入。\n" +
          "路径请使用正斜杠（如 ./temp/file）而非反斜杠，以避免与转义序列混淆。"
        )
      }
    },
  }
}) satisfies Plugin
