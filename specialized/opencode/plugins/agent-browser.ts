import type { Plugin } from "@opencode-ai/plugin";
import { spawnSync } from "node:child_process";

// agent-browser on Windows: the Rust binary's Command::spawn() defaults to
// bInheritHandles=TRUE, causing the daemon to inherit stdout/stderr pipe handles
// from PowerShell's output capture. PowerShell waits for all write-ends to close,
// hanging indefinitely. Use Node.js spawnSync with stdio:ignore to ensure no pipe
// handles leak to the daemon. See: https://github.com/vercel-labs/agent-browser/issues/1407
//
// PowerShell interprets bare @ as splat operator. Always wrap refs in single quotes:
//   agent-browser click '@e2'

const agentBrowserRe = /\bagent-browser\b/;

// 通过官方 session info 命令查询当前是否已有 agent-browser 会话（daemon）在运行，
// 不依赖内部 pid/socket 文件。仅在 daemon 未运行时返回 false，由调用方决定是否 open 拉起 daemon。
function hasRunningSession(): boolean {
  const probe = spawnSync("agent-browser", ["session", "info", "--json"], {
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
    encoding: "utf8",
    timeout: 3000,
  });
  if (probe.status !== 0 || !probe.stdout) return false;
  try {
    return JSON.parse(probe.stdout)?.data?.active === true;
  } catch {
    return false;
  }
}

export default (async () => {
  return {
    "tool.execute.before": async (input, output) => {
      const tool = String(input?.tool ?? "").toLowerCase();
      if (tool !== "bash" && tool !== "shell") return;

      const command = String(output?.args?.command ?? "");
      if (!command || !agentBrowserRe.test(command)) return;

      // PowerShell interprets bare @ as splat operator.
      // Detect @eN refs not wrapped in quotes (' " `).
      if (/(?:^|\s)@e\d/.test(command) && !/['"`]@e\d/.test(command)) {
        throw new Error(
          "[agent-browser] 检测到未加引号的 @ 引用（如 @eN），PowerShell 会将 @ 解释为 splat 操作符。\n" +
            "请使用单引号包裹 ref：agent-browser click '@e2'"
        );
      }

      // agent-browser#1407: ensure daemon is running synchronously before the
      // PowerShell command starts. Daemon may exit on its own (idle timeout,
      // crash, `close` tool call).
      if (!hasRunningSession()) {
        spawnSync("agent-browser", ["get", "url"], {
          stdio: "ignore",
          windowsHide: true,
          shell: true,
        });
      }
    },
  };
}) satisfies Plugin;
