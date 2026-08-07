import type { Plugin } from "@opencode-ai/plugin";
import { fileURLToPath } from "node:url";
import path from "node:path";

const PROFILE = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "agent-profile.ps1"
);
const PREFIX = `& "${PROFILE}"; `;

export default (async () => {
  return {
    "tool.execute.before": async (input, output) => {
      if (input.tool === "bash" && typeof output.args?.command === "string") {
        output.args.command = PREFIX + output.args.command;
      }
    },
  };
}) satisfies Plugin;
