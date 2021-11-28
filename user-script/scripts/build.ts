import { build } from "esbuild";

import { basename } from "path";
import { readFile, readdir } from "fs/promises";
import { createHash } from "crypto";

import { execSync } from "child_process";
import * as moment from "moment";
const METADATA_START = "// ==UserScript==";
const METADATA_END = "// ==/UserScript==";

function shell(command) {
  return execSync(command).toString().trimEnd();
}

function autoVersion(p: string): string {
  let date = new Date();
  try {
    date = new Date(parseInt(shell(`git log -1 --pretty=%at ${p}`)) * 1e3);
  } catch {
    console.warn(`can not get commit date: ${p}`);
  }

  return moment(date).format("YYYY.MM.DD");
}

async function getMetadataBlock(p: string): Promise<string> {
  const content = await readFile(p);
  const lines: string[] = [];
  let started = false;
  let versionLine = `// @version   ${autoVersion(p)}`;
  for (const line of content.toString().split(/\r?\n/)) {
    if (line === METADATA_START) {
      started = true;
      continue;
    }
    if (line === METADATA_END) {
      break;
    }
    if (started && line.startsWith("//")) {
      if (line.startsWith("// @version")) {
        versionLine = line;
      } else {
        lines.push(line);
      }
    }
  }

  // add hash to version
  const hash = createHash("sha256").update(content).digest("hex").slice(0, 8);
  lines.push(versionLine.trim() + `+${hash}`);

  return [METADATA_START, ...lines, METADATA_END].join("\n") + "\n";
}

(async () => {
  await Promise.all(
    (
      await readdir("./")
    )
      .filter((i) => i.endsWith(".ts"))
      .map(async (entry) => {
        const outfile = `dist/${basename(entry, ".ts")}.js`;
        const res = await build({
          entryPoints: [entry],
          banner: { js: await getMetadataBlock(entry) },
          bundle: true,
          target: "es2015",
          outfile,
          charset: "utf8",
          loader: {
            ".html": "text",
            ".css": "text",
          },
        });
        res.warnings.forEach((i) => {
          console.warn(i);
        });
        res.errors.forEach((i) => {
          console.error(i);
        });
        console.log(outfile);
      })
  );
})();
