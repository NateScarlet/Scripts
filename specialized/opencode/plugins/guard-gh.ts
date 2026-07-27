import { type Plugin, tool } from "@opencode-ai/plugin";
import { readFileSync, appendFileSync, mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { homedir } from "node:os";
import { execSync } from "node:child_process";

// #region 禁止 gh 命令包含 --repo，防止操作到错误仓库

const ghRepoRe = /\bgh\b.*--repo\b|--repo\b.*\bgh\b/i;

const knownReposPath = resolve(
  homedir(),
  ".config",
  "known_github_repositories"
);

const getKnownRepos = (): Set<string> => {
  try {
    const content = readFileSync(knownReposPath, "utf-8");
    return new Set(
      content
        .split("\n")
        .map((l) => l.trim())
        .filter((l) => l && !l.startsWith("#"))
    );
  } catch {
    return new Set();
  }
};

const getRepoValue = (command: string): string | null => {
  const match = command.match(/--repo[= ](['"]?)([^'"\s]+)\1/i);
  return match?.[2] ?? null;
};

const repoUrlRe = /(?:github\.com[:/])([\w.-]+\/[\w.-]+?)(?:\.git)?$/;

const getCurrentRepo = (): string | null => {
  try {
    const remoteOut = execSync("git remote get-url origin 2>nul", {
      encoding: "utf-8",
      stdio: "pipe",
    }).trim();
    if (!remoteOut) {
      return null;
    }
    return remoteOut;
  } catch {
    return null;
  }
};

// #endregion

export default (async () => {
  return {
    tool: {
      "guard-gh-allow": tool({
        description:
          "将仓库添加到 guard-gh 的放行列表，允许 gh --repo 访问该仓库",
        args: {
          repo: tool.schema.string().describe("仓库标识，格式 owner/repo"),
        },
        async execute(args, context) {
          const repo = String(args.repo).trim();
          if (!repo || !repo.includes("/")) {
            return { output: "错误：仓库格式无效，请使用 owner/repo 格式" };
          }

          const known = getKnownRepos();
          if (known.has(repo)) {
            return { output: `"${repo}" 已在放行列表中` };
          }

          try {
            await context.ask({
              permission: "guard-gh-allow",
              patterns: [repo],
              always: [repo],
              metadata: { repo },
            });
          } catch {
            return { output: `已拒绝添加 "${repo}" 到放行列表` };
          }

          try {
            mkdirSync(resolve(homedir(), ".config"), { recursive: true });
            appendFileSync(knownReposPath, `${repo}\n`, "utf-8");
            return { output: `已添加 "${repo}" 到 guard-gh 放行列表` };
          } catch (e) {
            return { output: `添加失败：${e}` };
          }
        },
      }),
    },
    "tool.execute.before": async (input, output) => {
      const toolName = String(input?.tool ?? "").toLowerCase();
      if (toolName !== "bash" && toolName !== "shell") return;

      const args = output?.args;
      if (!args || typeof args !== "object") return;

      const command = (args as Record<string, unknown>).command;
      if (typeof command !== "string" || !command) return;

      if (!ghRepoRe.test(command)) return;

      const repoValue = getRepoValue(command);
      if (!repoValue) return;
      if (getKnownRepos().has(repoValue)) return;

      const currentRepo = getCurrentRepo();
      if (currentRepo) {
        const match = currentRepo.match(repoUrlRe);
        const currentName = match?.[1];
        if (
          currentName &&
          currentName.toLowerCase() === repoValue.toLowerCase()
        )
          return;
      }

      throw new Error(
        `[guard-gh] 当前仓库 remote：${currentRepo ?? "未设置 remote origin"}\n` +
          `请移除 gh 的 --repo 参数，默认应操作当前仓库。如需操作目标仓库，请使用 guard-gh-allow 工具放行 "${repoValue}"`
      );
    },
  };
}) satisfies Plugin;
