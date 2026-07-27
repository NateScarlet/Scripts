import type { Plugin } from "@opencode-ai/plugin"

export default (async () => {
  return {
    "shell.env": async (_input, output) => {
      const index = parseInt(output.env.GIT_CONFIG_COUNT ?? "0", 10)
      output.env[`GIT_CONFIG_KEY_${index}`] = "commit.gpgsign"
      output.env[`GIT_CONFIG_VALUE_${index}`] = "false"
      output.env.GIT_CONFIG_COUNT = String(index + 1)
    },
  }
}) satisfies Plugin
