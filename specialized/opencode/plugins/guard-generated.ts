import type { Plugin } from "@opencode-ai/plugin"
import { access, readFile } from "node:fs/promises"

// #region helpers

const isGeneratedFile = async (filePath: string): Promise<boolean> => {
  const parts = filePath.replace(/\\/g, "/").split("/")
  const basename = parts.pop() ?? ""

  // 1) 文件名以 _gen 结尾（含扩展名场景如 foo_gen.go）
  const stem = basename.split(".")[0]
  if (stem.endsWith("_gen")) return true

  // 2) 文件路径或父目录名称为 generated
  if (parts.includes("generated") || basename === "generated") return true

  // 3) 首行包含 DO NOT EDIT
  try {
    await access(filePath)
    const content = await readFile(filePath, "utf-8")
    const firstLine = content.split("\n")[0]
    if (firstLine?.includes("DO NOT EDIT")) return true
  } catch {
    // 文件不存在则无需检查内容
  }

  return false
}

// #endregion

export default (async () => {
  return {
    "tool.execute.before": async (input, output) => {
      const tool = String(input?.tool ?? "").toLowerCase()
      if (tool !== "edit" && tool !== "write") return

      const args = output?.args
      if (!args || typeof args !== "object") return

      const filePath = (args as Record<string, unknown>).filePath
      if (typeof filePath !== "string" || !filePath) return

      if (!(await isGeneratedFile(filePath))) return

      throw new Error(`[guard] 禁止修改生成的文件: ${filePath}`)
    },
  }
}) satisfies Plugin
