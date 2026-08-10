import type { Plugin } from "@opencode-ai/plugin";
import { fileURLToPath } from "node:url";
import path from "node:path";

const PROFILE = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "agent-profile.ps1"
);
const PREFIX = `& $env:AGENT_PROFILE; `;

export default (async ({ worktree }) => {
  // bash 命令可能在子目录运行，scratch 目录固定挂在项目根目录（git 工作树）
  const SCRATCH_DIR = path.join(worktree, ".scratch");

  return {
    "shell.env": async (_input, output) => {
      output.env.AGENT_PROFILE = PROFILE;
      output.env.SCRATCH_DIR = SCRATCH_DIR;
    },
    "tool.execute.before": async (input, output) => {
      if (input.tool === "bash" && typeof output.args?.command === "string") {
        // agent 可能从历史命令中惯性复制前缀，避免重复注入导致 profile 执行两次
        if (!output.args.command.includes("& $env:AGENT_PROFILE")) {
          output.args.command = PREFIX + output.args.command;
        }
      }
    },
  };
}) satisfies Plugin;
