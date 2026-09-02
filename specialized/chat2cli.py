#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml>=6.0",
# ]
# ///
# pyright: strict

"""
chat2cli.py - chat2cli 语言执行器

从 stdin 读取文本，提取 ```chat2cli 代码块，在代码块内解析
<data.xxx> 数据标签和 <request> RPC 请求标签，解析 JSON-RPC 2.0 请求，
执行本地操作（文件替换或 PowerShell 命令），并将结果以 JSON-RPC 2.0
响应格式（同样用 chat2cli 代码块承载）输出到 stdout。
输入为空或无 chat2cli 代码块时，输出初始指令。

代码块之外的 <data.xxx> / <request> 等标签一律视为一般对话文本。

典型用法（PowerShell）:
    Get-Clipboard | python chat2cli.py | Set-Clipboard

每个版本的 chat2cli 不互相兼容，同一个会话应该固定用同一个版本
"""

from __future__ import annotations

import argparse
import os
import sys

# 设置 PYTHONIOENCODING，确保子 Python 进程也以 UTF-8 输出，
# 避免 Windows 控制台 GBK 代码页下出现中文乱码。
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import difflib
import json
import logging
import re
import signal
import subprocess
import tempfile
import threading
import traceback
from datetime import date

import yaml
from typing import Any, Dict, List, Optional, Tuple, cast

# 确保输入输出使用 UTF-8（避免 Windows 默认编码问题）
try:
    sys.stdin.reconfigure(encoding="utf-8")  # type: ignore
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore
except AttributeError:
    pass


# 已发现的 skills 缓存（name -> 信息字典）
_discovered_skills: Dict[str, Dict[str, Any]] = {}

# 输出超过该长度（字符数）时，写入 scratch 文件返回路径提示，不再走 OOB 块
_FILE_THRESHOLD = 8000
# OOB 数据块（<data.{id}>...</data.{id}>）与 ref 返回值的近似总开销（字符数）
_OOB_OVERHEAD_ESTIMATE = 80
# 待输出的带外数据（ref_id -> 内容），由 main 循环在 stdout 统一输出
_pending_oob_data: Dict[str, str] = {}


def _parse_skill_frontmatter(skill_md_path: str) -> Tuple[str, str]:
    """解析 SKILL.md 的 YAML frontmatter，返回 (name, description)。"""
    with open(skill_md_path, "r", encoding="utf-8") as f:
        content = f.read()

    if not content.startswith("---"):
        return "", ""

    end_idx = content.find("\n---", 3)
    if end_idx == -1:
        return "", ""

    frontmatter = content[3:end_idx]
    try:
        loaded_metadata = yaml.safe_load(frontmatter)
    except yaml.YAMLError as e:
        raise ValueError(f"SKILL.md YAML 解析失败: {e}") from e

    if not isinstance(loaded_metadata, dict):
        raise ValueError("SKILL.md frontmatter 必须是 YAML 字典格式")

    metadata: Dict[str, Any] = cast(Dict[str, Any], loaded_metadata)

    name = metadata.get("name", "")
    description = metadata.get("description", "")

    if not isinstance(name, str):
        name = ""
    if not isinstance(description, str):
        description = ""

    return name, description


def discover_skills() -> Dict[str, Dict[str, Any]]:
    """扫描 ~/.agents/skills 和 <cwd>/.agents/skills，发现可用 skills"""
    global _discovered_skills

    skills: Dict[str, Dict[str, Any]] = {}
    # 扫描顺序：先用户级，后项目级（项目级覆盖用户级）
    scan_dirs = [
        ("user", os.path.expanduser("~/.agents/skills")),
        ("project", os.path.join(os.getcwd(), ".agents/skills")),
    ]

    for scope, base_dir in scan_dirs:
        if not os.path.isdir(base_dir):
            continue
        try:
            entries = sorted(os.listdir(base_dir))
        except OSError as e:
            raise RuntimeError(f"无法读取 skill 目录 {base_dir}: {e}") from e

        for entry in entries:
            # 跳过隐藏目录和常见非 skill 目录
            if entry.startswith(".") or entry == "node_modules":
                continue
            skill_dir = os.path.join(base_dir, entry)
            if not os.path.isdir(skill_dir):
                continue
            skill_md = os.path.join(skill_dir, "SKILL.md")
            if not os.path.isfile(skill_md):
                continue

            name, description = _parse_skill_frontmatter(skill_md)
            if not name:
                # frontmatter 缺失时回退到目录名
                name = entry

            skills[name] = {
                "name": name,
                "description": description,
                "path": skill_dir,
                "scope": scope,
            }

    _discovered_skills = skills
    return skills


def print_instruction():
    """输出初始系统环境提示词，用于指导模型调用RPC"""
    cwd = os.getcwd()
    instruction = f"""<chat2cli_instruction>
你是一个通过在正文提供 chat2cli 代码块调用用户本地 RPC 方法辅助工作的助手，不依赖于工具注册即可操作用户环境。

chat2cli 是一种在用户本地把对话转换为可执行命令的语言。
它的完整语法都写在语言标记为 chat2cli 的围栏代码块中：

```chat2cli
<data.数据块id>
作为字面文本的数据内容
</data.数据块id>
<request>
JSON-RPC 2.0 请求（单个对象或对象数组，数组按顺序执行）
</request>
```

系统将只识别并处理 ```chat2cli 代码块内的 <data.xxx> 数据标签和 <request> RPC 请求标签。
代码块之外出现的 <data.xxx>、<request> 等标签一律只视为一般对话文本，不会被解析或执行。
如果你需要调用工具，请务必将标签放在该代码块中，否则任务将无法完成。

执行 chat2cli 调用时，请在代码块前提供一句简短的操作意图说明，不要描述详细推理过程。
按以下 response_template 输出调用请求：

<response_template>
{{此处替换为你的操作意图}}：
```chat2cli
<request>
{{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "pwsh",
  "params": {{
    "command": "在此填写要执行的命令"
  }}
}}
</request>
```
</response_template>

chat2cli 代码块可以出现在正文的任意位置，也可以前后补充必要的说明文字，
但代码块本身必须完整地出现在正文回复中，RPC 调用才可被用户复制执行。

带外数据（OOB）引用规则：
- 在 chat2cli 代码块内用数据标签定义数据块：<data.{{id}}>...</data.{{id}}>，块内为纯文本，零转义（反斜杠、引号、换行原样保留）。
- 在 <request> 的 params 中用对象引用：{{"id": "数据块id"}}，执行时会被替换为对应块内容。
- 字符串参数字面量不做替换，普通文本（即使以 # 开头）保持不变。
- data 块内容需要包含字面的反引号围栏（如 ``` 或 ``````）时，外层 chat2cli 围栏应使用比内容中任何反引号围栏都更长的反引号序列。例如内容包含 ``` 时，外层用 ````chat2cli ... ````；解析器会按围栏长度精确匹配闭合。

示例：用 gh 创建 issue，标题和正文通过 data 块传入。
推荐优先使用 data 块，内容零转义：
```chat2cli
<data.issue_title>fix(chat2cli): should skip chat2rpc inside data blocks</data.issue_title>
<data.issue_body>
## Problem

A data block's chat2cli fence is literal content, not a request.

Closes #42
</data.issue_body>
<request>
{{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "pwsh",
  "params": {{
    "command": "gh issue create --title $env:DATA_issue_title --body $env:DATA_issue_body"
  }}
}}
</request>
```

同一内容若不用环境变量和 data 块，需要把 PowerShell 字符串和 JSON 各转义一层：
```chat2cli
<request>
{{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "pwsh",
  "params": {{
    "command": "gh issue create --title 'fix(chat2cli): should skip request inside data blocks' --body '## Problem\\n\\nA data block''s request fence is literal content, not a request.\\n\\nCloses #42'"
  }}
}}
</request>

- 正文中定义的 <data.{{id}}> 数据块会注入为环境变量 `$env:DATA_{{id}}`，可在命令中直接引用。
- 响应中的大段内容也会以 <data.{{ref_id}}>...</data.{{ref_id}}> 块返回，并在 JSON 中给出 {{"ref": "ref_id"}} 引用。

可用方法：

1. str_replace_editor - 自定义编辑RPC（查看、创建、编辑文件）：
{{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "str_replace_editor",
  "params": {{
    "command": "view",
    "path": "文件或目录的绝对路径"
  }}
}}
- path 必须是绝对路径，且只能指向当前工作目录内的文件或目录。
- command 支持四种子命令，各子命令所需字段如下：

  1) view — 查看文件或目录
     必填：command, path
     可选：offset（起始行号，1 起）、limit（最大行数，默认 2000）
     · path 指向文件：显示带行号的内容（cat -n 效果）
     · path 指向目录：列出非隐藏项，最多 2 层

  2) create — 创建新文件（path 已存在时报错）
     必填：command, path, file_text
     · file_text：要写入的文件内容

  3) str_replace — 替换文件中的文本
     必填：command, path, old_str
     可选：new_str（缺省表示删除 old_str）
     · old_str 必须在文件中唯一匹配，建议包含上下文

  4) insert — 在指定行后插入文本
     必填：command, path, insert_line, new_str
     · insert_line：目标行号（1 起），new_str 插入到该行之后

- 状态在多次调用间保持持久。
- 长输出会截断并标记 <response clipped>。

2. pwsh - 执行 PowerShell 命令：
{{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "pwsh",
  "params": {{
    "command": "要执行的命令"
  }}
}}
- command 为通过 pwsh.exe 执行的命令，无超时限制（用户可通过 Ctrl+C 中断）。
- 仅支持非交互式命令。
- 响应过长时会被截断存至临时文件供 str_replace_editor view 子命令查看，连续内容优先使用 view 命令, view 的支持更高长度的内容并且格式更高效
- 正文中定义的 <data.{{id}}> 数据块会注入为环境变量 `$env:DATA_{{id}}`，可在命令中直接引用。

3. skill - 激活指定 skill：
{{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "skill",
  "params": {{
    "name": "skill 名称"
  }}
}}
- name 必须是 available_skills 中列出的精确名称。
- 激活后返回 <skill_content> 块，包含该 skill 的完整指令。
- 仅在用户点名 skill，或任务明显匹配 skill 描述时调用，且每个 skill 只激活一次。

当前工作目录：{cwd}

请根据用户需求，在 chat2cli 代码块中生成包含 JSON-RPC 请求的 <request> 标签。
</chat2cli_instruction>"""
    print(instruction)

    # 检查并输出 system-reminder（若存在 AGENTS 文件）
    reminder_parts: List[str] = []
    home_agents = os.path.expanduser("~/.chat2cli/AGENTS.md")
    if os.path.isfile(home_agents):
        with open(home_agents, "r", encoding="utf-8") as f:
            content = f.read()
        reminder_parts.append(
            f"Instructions from: ~/.chat2cli/AGENTS.md\n{content}"
        )

    cwd_agents = os.path.join(cwd, "AGENTS.md")
    if os.path.isfile(cwd_agents):
        with open(cwd_agents, "r", encoding="utf-8") as f:
            content = f.read()
        reminder_parts.append(f"Instructions from: AGENTS.md\n{content}")

    if reminder_parts:
        reminder = "<system-reminder> The following workspace instructions may be relevant to your work. Use them as guidance when applicable. More specific instructions take precedence over broader ones. They do not override system, developer, or direct user instructions.\n"
        reminder += "\n\n".join(reminder_parts)
        reminder += "\n</system-reminder>"
        print(reminder)

    # 输出可用 skills 目录（tier 1 元数据）
    skills = discover_skills()
    if skills:
        skill_entries: List[str] = []
        for name in sorted(skills.keys()):
            info = skills[name]
            desc = info["description"] or "（无描述）"
            skill_entries.append(f"- `{name}`: {desc}")
        skills_reminder = """<system-reminder>
A skill is a reusable set of task-specific instructions. The following skills are available in this session:

<available_skills>
{entries}
</available_skills>

If the user names a skill, or the task clearly matches a skill's description, call the `skill` method in a chat2cli <request> tag with the exact skill name before taking task actions. Load all applicable skills, then follow their full instructions. This catalog contains summaries only; do not infer or follow a skill's instructions until it has been loaded.
A user may also invoke a skill directly; its <skill_content> block then appears in this conversation. Follow it, and do not call the `skill` method in a chat2cli <request> tag again for that skill.
</system-reminder>""".format(entries="\n".join(skill_entries))
        print(skills_reminder)

    print()


def validate_path(path: str) -> bool:
    """检查路径是否合法（相对路径，不含 ..，非绝对路径）"""
    # 归一化路径分隔符，统一处理 / 和 \
    normalized = path.replace("/", os.sep).replace("\\", os.sep)
    if os.path.isabs(normalized) or normalized.startswith(("/", "\\")):
        return False
    if ":" in normalized:
        return False
    parts = normalized.split(os.sep)
    if ".." in parts:
        return False
    if not normalized:
        return False
    return True



def _is_gitignored(path: str) -> bool:
    """检查路径是否被 gitignore 忽略。"""
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", "--", path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=os.getcwd(),
    )
    return result.returncode == 0


def _colorize_ignored_path(path: str) -> str:
    """将 gitignore 忽略的路径部分使用橙色显示。"""
    if not _is_gitignored(path):
        return path

    try:
        cwd = os.path.abspath(os.getcwd())
        abs_path = os.path.abspath(path)
        if abs_path.startswith(cwd + os.sep):
            rel = os.path.relpath(abs_path, cwd)
            parts = rel.split(os.sep)
            ignored_index = 0
            for i in range(len(parts)):
                candidate = os.path.join(cwd, *parts[: i + 1])
                if _is_gitignored(candidate):
                    ignored_index = i
                    break
            normal = os.sep.join(parts[:ignored_index])
            ignored = os.sep.join(parts[ignored_index:])
            if normal:
                return f"{normal}{os.sep}\033[38;5;208m{ignored}\033[0m"
            return f"\033[38;5;208m{ignored}\033[0m"
        # 路径不在当前工作目录内，直接返回带颜色的原始路径
        return f"\033[38;5;208m{path}\033[0m"
    except Exception:
        # 路径处理过程中出现异常时返回普通格式
        return f"\033[38;5;208m{path}\033[0m"



def _read_text_file(path: str) -> Tuple[str, str]:
    """读取文本文件，返回 (内容, 使用的编码)。"""
    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            return f.read(), "utf-8"
    except UnicodeDecodeError:
        import locale
        encoding = locale.getpreferredencoding(False)
        with open(path, "r", encoding=encoding, newline="") as f:
            return f.read(), encoding


def _write_text_file_atomic(path: str, content: str, encoding: str = "utf-8") -> None:
    """原子写入文本文件，避免写入中断导致目标文件损坏。"""
    directory = os.path.dirname(os.path.abspath(path))
    fd, temp_path = tempfile.mkstemp(dir=directory, prefix=".chat2cli-")
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError as e:
            # 删除临时文件失败不影响主流程，但需要提醒
            sys.stderr.write(f"警告：无法删除临时文件 {temp_path}: {e}\n")
            sys.stderr.flush()
        raise



def _normalize_newlines(text: str) -> str:
    """将 CRLF 和 CR 统一规范化为 LF"""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _find_closest_line(content: str, old_normalized: str) -> str:
    """窗口滑动匹配：锚定 old 首行，整体比较后续行，返回差异提示"""
    if not content or not old_normalized:
        return ""

    content_lines = content.split("\n")
    old_lines = old_normalized.split("\n")
    first_old_line = old_lines[0]

    # 第一步：找 old 首行在文件中的所有候选位置（相似度 > 0.5）
    candidates: List[Tuple[int, float]] = []
    for idx, line in enumerate(content_lines):
        ratio = difflib.SequenceMatcher(None, line, first_old_line).ratio()
        if ratio > 0.5:
            candidates.append((idx, ratio))

    if not candidates:
        return ""

    # 第二步：对每个候选位置，计算 old 整体与文件对应窗口的匹配分数
    # 分数 = 首行相似度 * 2 + 后续行相似度总和（首行权重更高）
    best_window_idx = -1
    best_window_score = -1.0
    for content_idx, first_ratio in candidates:
        score = first_ratio * 2.0
        for old_offset in range(1, len(old_lines)):
            file_line_idx = content_idx + old_offset
            if file_line_idx < len(content_lines):
                line_ratio = difflib.SequenceMatcher(
                    None, content_lines[file_line_idx], old_lines[old_offset]
                ).ratio()
                score += line_ratio
            # 文件窗口不够长时不给加分（视为不匹配）
        # 归一化分数
        score = score / (2.0 + len(old_lines) - 1)
        if score > best_window_score:
            best_window_score = score
            best_window_idx = content_idx

    if best_window_idx == -1:
        return ""

    # 第三步：在最佳窗口内找第一处不匹配的行
    first_bad_old_idx = -1
    first_bad_file_idx = -1
    first_bad_ratio = 0.0
    for old_offset in range(len(old_lines)):
        file_line_idx = best_window_idx + old_offset
        if file_line_idx >= len(content_lines):
            first_bad_old_idx = old_offset
            first_bad_file_idx = file_line_idx
            first_bad_ratio = 0.0
            break
        ratio = difflib.SequenceMatcher(
            None, content_lines[file_line_idx], old_lines[old_offset]
        ).ratio()
        if ratio < 0.999:
            first_bad_old_idx = old_offset
            first_bad_file_idx = file_line_idx
            first_bad_ratio = ratio
            break

    if first_bad_old_idx == -1:
        # 窗口内所有行都匹配，检查行数差异
        window_len = min(len(old_lines), len(content_lines) - best_window_idx)
        if len(old_lines) > window_len:
            extra = old_lines[window_len:window_len + 3]
            return (
                f"old 在文件第 {best_window_idx + 1} 行处匹配了前 {window_len} 行，"
                f"但 old 还有 {len(old_lines) - window_len} 行，文件此处已结束。\n"
                f"  old 多出的行：\n"
                + "\n".join(f"    {i + window_len + 1}: {line!r}" for i, line in enumerate(extra))
            )
        elif len(old_lines) < window_len:
            extra = content_lines[best_window_idx + len(old_lines):best_window_idx + len(old_lines) + 3]
            return (
                f"old 在文件第 {best_window_idx + 1} 行处匹配了前 {len(old_lines)} 行，"
                f"但文件此处后续还有 {window_len - len(old_lines)} 行 old 没有包含。\n"
                f"  文件多出的行：\n"
                + "\n".join(f"    {i + len(old_lines) + 1}: {line!r}" for i, line in enumerate(extra))
            )
        return ""

    file_line = content_lines[first_bad_file_idx] if first_bad_file_idx < len(content_lines) else ""
    old_line = old_lines[first_bad_old_idx]

    # 生成该行的逐字符 diff
    sm_line = difflib.SequenceMatcher(None, file_line, old_line, autojunk=False)
    diff_parts: List[str] = []
    for tag, i1, i2, j1, j2 in sm_line.get_opcodes():
        if tag == "equal":
            eq_text = file_line[i1:i2]
            if len(eq_text) > 40:
                eq_text = "..." + eq_text[-37:]
            diff_parts.append(f"    相同：{eq_text!r}")
        elif tag == "replace":
            diff_parts.append(f"  - 文件：{file_line[i1:i2]!r}")
            diff_parts.append(f"  +  old：{old_line[j1:j2]!r}")
        elif tag == "delete":
            diff_parts.append(f"  - 文件多出：{file_line[i1:i2]!r}")
        elif tag == "insert":
            diff_parts.append(f"  +  old 多出：{old_line[j1:j2]!r}")

    diff_text = "\n".join(diff_parts)

    # 缩进专项分析：如果差异只涉及行首空白，给出明确修复建议
    indent_hint = ""
    file_leading = len(file_line) - len(file_line.lstrip(" \t"))
    old_leading = len(old_line) - len(old_line.lstrip(" \t"))
    file_indent = file_line[:file_leading]
    old_indent = old_line[:old_leading]
    if file_indent != old_indent and file_line.lstrip(" \t") == old_line.lstrip(" \t"):
        # 两行去除行首空白后完全相同 → 纯缩进差异
        file_spaces = file_indent.count(" ")
        old_spaces = old_indent.count(" ")
        if file_spaces > old_spaces:
            indent_hint = (
                f"\n  缩进修复建议：文件缩进是 {file_spaces} 个空格，"
                f"old 是 {old_spaces} 个空格。"
                f"请在 old 开头增加 {file_spaces - old_spaces} 个空格。"
            )
        elif file_spaces < old_spaces:
            indent_hint = (
                f"\n  缩进修复建议：文件缩进是 {file_spaces} 个空格，"
                f"old 是 {old_spaces} 个空格。"
                f"请从 old 开头删除 {old_spaces - file_spaces} 个空格。"
            )
        elif "\t" in file_indent or "\t" in old_indent:
            file_tabs = file_indent.count("\t")
            old_tabs = old_indent.count("\t")
            indent_hint = (
                f"\n  缩进修复建议：文件用 {file_tabs} 个 tab，old 用 {old_tabs} 个 tab。"
                f"请调整 old 的缩进。"
            )

    return (
        f"第一处不匹配：old 第 {first_bad_old_idx + 1} 行 ↔ 文件第 {first_bad_file_idx + 1} 行"
        f"（行相似度 {first_bad_ratio:.0%}）：\n"
        f"{diff_text}"
        f"{indent_hint}\n"
        f"  提示：请检查缩进、空白字符、标点或换行是否一致。"
    )


def _detect_dominant_newline(raw_content: str) -> str:
    """检测文件主要换行风格，返回 '\r\n'、'\n' 或 '\r'"""
    crlf_count = raw_content.count("\r\n")
    lf_count = raw_content.count("\n") - crlf_count
    cr_count = raw_content.count("\r") - crlf_count
    if crlf_count >= lf_count and crlf_count >= cr_count:
        return "\r\n"
    elif lf_count >= cr_count:
        return "\n"
    else:
        return "\r"


def _restore_newlines(text: str, newline_style: str) -> str:
    """将规范化的 LF 恢复为指定的换行风格"""
    if newline_style == "\n":
        return text
    return text.replace("\n", newline_style)


def _calculate_line_changes(before: str, after: str) -> Dict[str, int]:
    """计算文本修改造成的行级变化。"""
    import difflib

    before_lines = before.split("\n")
    after_lines = after.split("\n")
    matcher = difflib.SequenceMatcher(None, before_lines, after_lines, autojunk=False)

    removed_lines = 0
    added_lines = 0
    modified_lines = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "delete":
            removed_lines += i2 - i1
        elif tag == "insert":
            added_lines += j2 - j1
        elif tag == "replace":
            modified_lines += max(i2 - i1, j2 - j1)

    return {
        "removed_lines": removed_lines,
        "added_lines": added_lines,
        "modified_lines": modified_lines,
    }



def execute_skill(id_: Any, params: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    """激活指定 skill，返回 (元数据, skill_content 内容块)"""
    name = params.get("name")
    if not isinstance(name, str) or not name:
        return {"success": False, "message": "错误：name 不能为空。"}, ""

    if not _discovered_skills:
        discover_skills()

    if name not in _discovered_skills:
        available = sorted(_discovered_skills.keys())
        avail_text = ", ".join(f"`{n}`" for n in available) if available else "无"
        return {
            "success": False,
            "message": f"错误：未找到名为 `{name}` 的 skill。可用 skills：{avail_text}",
        }, ""

    skill_dir = os.path.abspath(_discovered_skills[name]["path"])
    skill_md_path = os.path.join(skill_dir, "SKILL.md")
    try:
        with open(skill_md_path, "r", encoding="utf-8") as f:
            raw_content = f.read()
    except Exception as e:
        return {"success": False, "message": f"错误：读取 SKILL.md 失败：{str(e)}"}, ""

    content_block = f"""<skill_content name="{name}">
<skill_resources>
Base directory for this skill: {skill_dir}
Resolve relative paths mentioned by this skill against the base directory before using them. Load referenced resources only as needed.
</skill_resources>

<skill_instructions>
{raw_content}
</skill_instructions>
</skill_content>
"""

    meta = {
        "success": True,
        "name": name,
        "path": skill_dir,
        "message": "Skill activated.",
    }
    return meta, content_block

def _resolve_editor_path(path_raw: str) -> str:
    """解析 str_replace_editor 的 path：必须为绝对路径且位于当前工作目录内"""
    expanded = os.path.expanduser(path_raw)
    if not os.path.isabs(expanded):
        return ""
    abs_path = os.path.abspath(expanded)
    cwd = os.path.abspath(os.getcwd())
    if abs_path == cwd:
        return abs_path
    if abs_path.startswith(cwd + os.sep):
        return abs_path
    return ""


def execute_str_replace_editor(id_: Any, params: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    """执行 str_replace_editor 命令（view/create/str_replace/insert），返回 (元数据, 内容块)"""
    import sys

    command = params.get("command")
    path_raw = params.get("path")

    if not isinstance(command, str) or command not in ("view", "create", "str_replace", "insert"):
        return {
            "success": False,
            "message": "错误：command 必须是 view、create、str_replace 或 insert。",
        }, ""
    if not isinstance(path_raw, str) or not path_raw:
        return {"success": False, "message": "错误：path 不能为空。"}, ""

    path = _resolve_editor_path(path_raw)
    if not path:
        sys.stderr.write(
            "\n[chat2cli] 路径校验失败：操作范围仅限当前工作目录（cwd）。\n"
            f"[chat2cli] 您请求的路径：{path_raw}\n"
            f"[chat2cli] 请用户切换到对应目录（{os.path.dirname(path_raw)}）后再执行此方法。\n\n"
        )
        sys.stderr.flush()
        return {
            "success": False,
            "message": "错误：path 必须是绝对路径，且只能指向当前工作目录内的文件或目录。如需操作目录外的文件，请提示用户在对应目录下重新运行此方法。",
        }, ""

    if command == "view":
        if os.path.isdir(path):
            return view_directory(id_, path)
        elif os.path.isfile(path):
            return view_file(id_, path, params)
        else:
            return {"success": False, "message": f"错误：路径不存在：{path}"}, ""

    elif command == "create":
        if os.path.exists(path):
            return {"success": False, "message": f"错误：文件已存在：{path}"}, ""
        file_text = params.get("file_text")
        if not isinstance(file_text, str):
            return {"success": False, "message": "错误：create 命令需要 file_text 参数（字符串）。"}, ""
        try:
            _write_text_file_atomic(path, file_text, "utf-8")
        except Exception as e:
            return {"success": False, "message": f"错误：创建文件失败：{str(e)}"}, ""
        abs_path = os.path.abspath(path)
        sys.stderr.write(f"\033[36m📝 str_replace_editor create {abs_path}\033[0m\n")
        sys.stderr.write("\033[32m+++ 写入内容:\033[0m\n")
        sys.stderr.write(file_text)
        if not file_text.endswith("\n"):
            sys.stderr.write("\n")
        sys.stderr.write("\033[32m+++ 写入结束\033[0m\n")
        sys.stderr.flush()
        return {
            "success": True,
            "path": abs_path,
            "message": f"文件已创建：{abs_path}",
        }, ""

    elif command == "str_replace":
        if not os.path.isfile(path):
            return {"success": False, "message": "错误：文件不存在。"}, ""
        old_str = params.get("old_str")
        new_str = params.get("new_str", "")
        if not isinstance(old_str, str) or not old_str:
            return {"success": False, "message": "错误：old_str 字符串不能为空。"}, ""
        if not isinstance(new_str, str):
            return {"success": False, "message": "错误：new_str 必须是字符串。"}, ""
        return _str_replace_file(id_, path, old_str, new_str), ""

    elif command == "insert":
        if not os.path.isfile(path):
            return {"success": False, "message": "错误：文件不存在。"}, ""
        insert_line = params.get("insert_line")
        new_str = params.get("new_str")
        if not isinstance(insert_line, int) or isinstance(insert_line, bool) or insert_line < 1:
            return {"success": False, "message": "错误：insert_line 必须是 >=1 的整数。"}, ""
        if not isinstance(new_str, str):
            return {"success": False, "message": "错误：new_str 必须是字符串。"}, ""
        return _insert_in_file(id_, path, insert_line, new_str), ""

    return {"success": False, "message": "未知错误。"}, ""


def view_file(id_: Any, path: str, params: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    """查看文件内容，返回 (元数据, 行号化内容)"""
    offset_param = params.get("offset", 1)
    limit_param = params.get("limit", 2000)
    if not isinstance(offset_param, int) or isinstance(offset_param, bool) or offset_param < 1:
        return {"success": False, "message": "错误：offset 必须是 >=1 的整数。"}, ""
    if not isinstance(limit_param, int) or isinstance(limit_param, bool) or limit_param < 1:
        return {"success": False, "message": "错误：limit 必须是 >=1 的整数。"}, ""

    encoding_to_use = "utf-8"
    try:
        with open(path, "r", encoding=encoding_to_use, newline="") as f:
            raw_content = f.read()
    except UnicodeDecodeError:
        import locale
        encoding_to_use = locale.getpreferredencoding(False)
        try:
            with open(path, "r", encoding=encoding_to_use, newline="") as f:
                raw_content = f.read()
        except Exception as e:
            return {"success": False, "message": f"错误：读取文件失败：{str(e)}"}, ""
    except Exception as e:
        return {"success": False, "message": f"错误：读取文件失败：{str(e)}"}, ""

    content = _normalize_newlines(raw_content)
    all_lines = content.split("\n")
    if all_lines and all_lines[-1] == "":
        all_lines = all_lines[:-1]
    total_lines = len(all_lines)

    start_idx = offset_param - 1
    end_idx = min(start_idx + limit_param, total_lines)
    if start_idx >= total_lines:
        selected: List[str] = []
    else:
        selected = all_lines[start_idx:end_idx]

    output_lines: List[str] = []
    for i, line in enumerate(selected):
        line_num = offset_param + i
        output_lines.append(f"{line_num}:{line}")
    content_out = "\n".join(output_lines)

    first_line = offset_param
    last_line = offset_param + len(selected) - 1 if selected else offset_param - 1
    meta: Dict[str, Any] = {
        "success": True,
        "path": os.path.abspath(path),
        "total_lines": total_lines,
        "returned_lines": len(selected),
        "first_line": first_line,
        "last_line": last_line,
        "message": "Read completed.",
    }

    if content_out:
        if last_line < total_lines:
            footer = f"\n(Showing lines {first_line}-{last_line} of {total_lines}. Use offset={last_line + 1} to continue.)"
        else:
            footer = f"\n(End of file - total {total_lines} lines)"
        content_with_footer = content_out + footer
    else:
        content_with_footer = f"(Showing lines {first_line}-{last_line} of {total_lines}.)"

    ref_id = _gen_view_oob_id(id_)
    content_block = _data_block_text(
        ref_id, f'{meta["path"]}:L{first_line}-{last_line}\n{content_with_footer}'
    ) + "\n"
    meta["content"] = {"ref": ref_id}
    # stderr 显示读取路径（gitignore 部分橙色高亮）
    sys.stderr.write(f"[chat2cli] view {_colorize_ignored_path(cast(str, meta['path']))}:L{first_line}-{last_line}\n")
    sys.stderr.flush()

    return meta, content_block


def view_directory(id_: Any, path: str) -> Tuple[Dict[str, Any], str]:
    """列出目录内容（非隐藏项，最多 2 层），返回 (元数据, 目录列表)"""
    try:
        entries = sorted(os.listdir(path))
    except Exception as e:
        return {"success": False, "message": f"错误：读取目录失败：{str(e)}"}, ""

    lines: List[str] = []
    for entry in entries:
        if entry.startswith("."):
            continue
        full = os.path.join(path, entry)
        if os.path.isdir(full):
            lines.append(f"{entry}/")
            try:
                sub_entries = sorted(os.listdir(full))
            except Exception as e:
                sys.stderr.write(f"警告：无法读取子目录 {full}: {e}\n")
                sys.stderr.flush()
                continue
            for sub in sub_entries:
                if sub.startswith("."):
                    continue
                sub_full = os.path.join(full, sub)
                if os.path.isdir(sub_full):
                    lines.append(f"  {sub}/")
                else:
                    lines.append(f"  {sub}")
        else:
            lines.append(entry)

    ref_id = _gen_view_oob_id(id_)
    dir_content = f"{os.path.abspath(path)}\n" + "\n".join(lines)
    content_block = _data_block_text(ref_id, dir_content) + "\n"
    # stderr 显示目录读取路径（gitignore 部分橙色高亮）
    sys.stderr.write(f"[chat2cli] view {_colorize_ignored_path(os.path.abspath(path))}\n")
    sys.stderr.flush()

    meta = {
        "success": True,
        "path": os.path.abspath(path),
        "entry_count": len(entries),
        "content": {"ref": ref_id},
        "message": "Directory listed.",
    }
    return meta, content_block


def _str_replace_file(id_: Any, path: str, old_str: str, new_str: str) -> Dict[str, Any]:
    """替换文件中的文本，返回 result 字典"""
    try:
        raw_content, encoding_to_use = _read_text_file(path)
    except Exception as e:
        return {"success": False, "message": f"错误：读取文件失败：{str(e)}"}

    newline_style = _detect_dominant_newline(raw_content)
    content = _normalize_newlines(raw_content)
    old_normalized = _normalize_newlines(old_str)
    new_normalized = _normalize_newlines(new_str)

    count = content.count(old_normalized)
    if count == 0:
        hint = _find_closest_line(content, old_normalized)
        if hint:
            return {
                "success": False,
                "message": f"错误：未找到匹配文本。可能的原因：\n{hint}",
            }
        return {"success": False, "message": "错误：未找到匹配文本。"}
    elif count > 1:
        return {
            "success": False,
            "message": f"错误：检测到 {count} 处匹配，无法唯一确定替换位置。请提供更长的 old_str 字符串。",
        }

    abs_path = os.path.abspath(path)
    old_lines = old_normalized.split("\n")
    new_lines = new_normalized.split("\n")

    if old_normalized == new_normalized:
        sys.stderr.write(f"\033[33m⚠️  str_replace_editor: old_str 和 new_str 内容相同，文件未修改: {abs_path}\033[0m\n")
        sys.stderr.flush()
        return {
            "success": False,
            "path": abs_path,
            "deleted_lines": 0,
            "added_lines": 0,
            "message": f"错误：old_str 和 new_str 内容相同，拒绝执行无效替换: {abs_path}",
        }

    new_content_normalized = content.replace(old_normalized, new_normalized, 1)
    new_content = _restore_newlines(new_content_normalized, newline_style)
    try:
        _write_text_file_atomic(path, new_content, encoding_to_use)
    except Exception as e:
        return {"success": False, "message": f"错误：写入文件失败：{str(e)}"}

    diff = difflib.unified_diff(
        old_lines, new_lines, fromfile=f"a/{path}", tofile=f"b/{path}", lineterm=""
    )
    diff_output = list(diff)
    if diff_output:
        sys.stderr.write(f"\033[36m📝 str_replace_editor 修改 {path}:\033[0m\n")
        for line in diff_output:
            if line.startswith("---") or line.startswith("+++"):
                sys.stderr.write(f"\033[36m{line}\033[0m\n")
            elif line.startswith("@@"):
                sys.stderr.write(f"\033[35m{line}\033[0m\n")
            elif line.startswith("-"):
                sys.stderr.write(f"\033[31m{line}\033[0m\n")
            elif line.startswith("+"):
                sys.stderr.write(f"\033[32m{line}\033[0m\n")
            else:
                sys.stderr.write(f"{line}\n")
        sys.stderr.flush()

    changes = _calculate_line_changes(content, new_content_normalized)
    return {
        "success": True,
        "path": abs_path,
        "changes": changes,
        "message": f"The file {abs_path} has been updated successfully.",
    }


def _insert_in_file(id_: Any, path: str, insert_line: int, new_str: str) -> Dict[str, Any]:
    """在指定行后插入文本，返回 result 字典"""
    try:
        raw_content, encoding_to_use = _read_text_file(path)
    except Exception as e:
        return {"success": False, "message": f"错误：读取文件失败：{str(e)}"}

    newline_style = _detect_dominant_newline(raw_content)
    content = _normalize_newlines(raw_content)
    content_lines = content.split("\n")
    if content_lines and content_lines[-1] == "":
        content_lines = content_lines[:-1]

    if insert_line > len(content_lines):
        return {
            "success": False,
            "message": f"错误：insert_line={insert_line} 超出文件行数 {len(content_lines)}。",
        }

    new_str_normalized = _normalize_newlines(new_str)
    # insert_line 表示目标行号，接口语义要求插入到该行之后。
    content_lines.insert(insert_line, new_str_normalized)
    new_content_normalized = "\n".join(content_lines)
    new_content = _restore_newlines(new_content_normalized, newline_style)

    try:
        _write_text_file_atomic(path, new_content, encoding_to_use)
    except Exception as e:
        return {"success": False, "message": f"错误：写入文件失败：{str(e)}"}

    abs_path = os.path.abspath(path)
    sys.stderr.write(f"\033[36m📝 str_replace_editor insert {abs_path}: 在第 {insert_line} 行后插入\033[0m\n")
    sys.stderr.write("\033[32m+++ 插入内容:\033[0m\n")
    sys.stderr.write(new_str)
    if not new_str.endswith("\n"):
        sys.stderr.write("\n")
    sys.stderr.write("\033[32m+++ 插入结束\033[0m\n")
    sys.stderr.flush()
    return {
        "success": True,
        "path": abs_path,
        "insert_after_line": insert_line,
        "inserted_start_line": insert_line + 1,
        "inserted_end_line": insert_line + new_str_normalized.count("\n") + 1,
        "message": f"The file {abs_path} has been updated successfully.",
    }


def _gen_view_oob_id(id_: Any) -> str:
    """生成 view 命令的带外数据引用 ID。

    view 响应总对应一个带 id 的请求，因此 id 一定存在。
    """
    return f"view_{id_}"


def _register_oob_data(ref_id: str, content: str) -> None:
    """注册带外数据，供 main 循环统一输出"""
    _pending_oob_data[ref_id] = content


def _data_block_text(ref_id: str, content: str) -> str:
    """生成带外数据块文本（使用 data.{id} 标签，原样保留内容，无包裹换行）"""
    return f"<data.{ref_id}>{content}</data.{ref_id}>"


def _scratch_filepath(id_: Any, stream_name: str, text: str) -> str:
    """将超长输出写入 scratch 文件，返回绝对路径"""
    scratch_dir = os.path.join(
        os.getcwd(), ".scratch", f"{date.today().isoformat()}-chat2cli"
    )
    os.makedirs(scratch_dir, exist_ok=True)
    safe_id = re.sub(r"[^\w\-.]", "_", str(id_))
    base_name = f"{stream_name}_{safe_id}"
    filepath = os.path.join(scratch_dir, f"{base_name}.txt")
    counter = 1
    while os.path.exists(filepath):
        filepath = os.path.join(scratch_dir, f"{base_name}_{counter}.txt")
        counter += 1
    with open(filepath, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return os.path.abspath(filepath)


def _format_viewed(text: str, start_line: int = 1) -> str:
    """以 view 相同格式渲染文本：每行前置行号，行号从 start_line 开始"""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    return "\n".join(
        f"{start_line + i}:{line}" for i, line in enumerate(lines)
    )


def _emit_result_text(id_: Any, stream_name: str, text: str) -> Any:
    """三层策略输出结果文本：
    1. 超长（>= _FILE_THRESHOLD）：写 scratch 文件，返回截断说明 + head/tail 引用
    2. JSON 编码膨胀显著（> OOB 开销估算）：返回 {"ref": ref_id}，内容进入 OOB 块
    3. 其余：直接内联字符串
    """
    if not text:
        return text

    # 超长：直接写文件，避免把几 MB 内容塞进剪贴板
    if len(text) >= _FILE_THRESHOLD:
        abs_path = _scratch_filepath(id_, stream_name, text)
        head_ref = f"{stream_name}_{id_}_head"
        tail_ref = f"{stream_name}_{id_}_tail"

        # 开头和结尾各取约内联最大长度的一半，按 view 格式（带行号）提供。
        # 截取边界按行对齐，保证 head 和 tail 都从完整行开始。
        half = _FILE_THRESHOLD // 2

        # head：从头取约 half 字符后，回溯到最近的换行处，只保留完整行
        head_raw = text[:half]
        head_cut = head_raw.rfind("\n")
        if head_cut != -1:
            head_raw = head_raw[:head_cut]
        head_text = _format_viewed(head_raw)

        # tail：从尾取约 half 字符后，前进到最近的换行处，只保留完整行
        tail_raw = text[-half:]
        tail_cut = tail_raw.find("\n")
        if tail_cut != -1:
            tail_raw = tail_raw[tail_cut + 1:]
        # tail 首行在全文中的行号：截取位置之前的换行数 + 1
        tail_start_char = len(text) - half + (tail_cut + 1 if tail_cut != -1 else 0)
        preceding_lines = text[:tail_start_char].count("\n")
        tail_text = _format_viewed(tail_raw, start_line=preceding_lines + 1)
        _register_oob_data(head_ref, head_text)
        _register_oob_data(tail_ref, tail_text)

        return {
            "message": (
                f"输出过长（{len(text)} 字符），完整内容已保存至: {abs_path}"
            ),
            "path": abs_path,
            "head": {"ref": head_ref},
            "tail": {"ref": tail_ref},
        }

    # 计算 JSON 编码膨胀（ensure_ascii=False 下主要来自引号、反斜杠、控制字符转义）
    json_encoded_len = len(json.dumps(text, ensure_ascii=False))
    encoding_overhead = json_encoded_len - len(text)

    if encoding_overhead > _OOB_OVERHEAD_ESTIMATE:
        ref_id = f"{stream_name}_{id_}"
        _register_oob_data(ref_id, text)
        return {"ref": ref_id}

    return text




def execute_pwsh(id_: Any, params: Dict[str, Any], data_map: Dict[str, str]) -> Dict[str, Any]:
    """执行 PowerShell 命令，实时输出到 stderr，返回 JSON-RPC result 字典"""
    command = params.get("command")

    if not isinstance(command, str) or not command.strip():
        return {"success": False, "message": "错误：command 不能为空。"}

    wrapped_command = (
        f"try {{ $PSStyle.OutputRendering = 'PlainText' }} catch {{}}; "
        f"$OutputEncoding = [System.Text.Encoding]::UTF8; "
        f"[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        f"$env:PYTHONIOENCODING = 'utf-8'; {command}"
    )

    # 为子进程补充 CI 环境变量：执行者始终是 agent，无交互终端，
    # CI=true 让 vitest 等工具默认进入非交互模式而非 watch；
    # NO_COLOR=1 禁用彩色输出，避免转义码污染捕获的文本。
    env = os.environ.copy()
    env["CI"] = "true"
    env["NO_COLOR"] = "1"

    # 将 <data.xxx> 数据块注入为 $env:DATA_xxx 环境变量。
    # 数据块 id 原样拼接为环境变量名。
    for ref_id, ref_content in data_map.items():
        env_name = "DATA_" + ref_id
        env[env_name] = ref_content

    def _stream_reader(stream: Any, stream_name: str, lines_list: List[str]) -> None:
        """逐行读取子进程输出，实时写入 stderr 并累积到列表"""
        try:
            for line in iter(stream.readline, ""):
                sys.stderr.write(f"[pwsh:{stream_name}] {line}")
                sys.stderr.flush()
                lines_list.append(line)
        finally:
            # 关闭流，忽略关闭时的异常
            try:
                stream.close()
            except OSError:
                pass

    try:
        proc = subprocess.Popen(
            ["pwsh.exe", "-NoProfile", "-Command", wrapped_command],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            stdin=subprocess.DEVNULL,
            env=env,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,  # 允许独立进程组管理
        )
    except FileNotFoundError:
        return {
            "success": False,
            "message": "错误：未找到 pwsh.exe，请确保 PowerShell Core 已安装并添加到 PATH。",
        }
    except Exception as e:
        return {"success": False, "message": f"错误：命令执行异常：{str(e)}"}

    stdout_lines: List[str] = []
    stderr_lines: List[str] = []
    t_out = threading.Thread(
        target=_stream_reader,
        args=(proc.stdout, "out", stdout_lines),
        daemon=True,
    )
    t_err = threading.Thread(
        target=_stream_reader,
        args=(proc.stderr, "err", stderr_lines),
        daemon=True,
    )
    t_out.start()
    t_err.start()

    # 设置信号处理器，在收到 SIGINT 时清理子进程
    def _signal_handler(sig: int, frame: Any) -> None:
        """处理 Ctrl+C 信号，清理子进程后退出"""
        sys.stderr.write("\n[chat2cli] 收到中断信号，正在清理 pwsh 进程...\n")
        sys.stderr.flush()
        try:
            # 终止进程组，确保所有子进程都被清理
            proc.terminate()
            # 等待一小段时间让进程优雅退出
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        except Exception as e:
            sys.stderr.write(f"[chat2cli] 清理子进程时发生错误: {e}\n")
            sys.stderr.flush()
        sys.exit(1)

    original_handler = signal.signal(signal.SIGINT, _signal_handler)

    try:
        # 无限等待，让命令自然结束
        returncode = proc.wait()
    except Exception as e:
        # 如果发生异常，确保清理进程
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception as cleanup_err:
            sys.stderr.write(f"[chat2cli] 清理子进程时发生错误: {cleanup_err}\n")
            sys.stderr.flush()
            try:
                proc.kill()
                proc.wait()
            except Exception:
                pass
        raise
    finally:
        # 恢复原始信号处理器
        signal.signal(signal.SIGINT, original_handler)

    t_out.join(timeout=5)
    t_err.join(timeout=5)

    stdout = "".join(stdout_lines).rstrip("\n")
    stderr = "".join(stderr_lines).rstrip("\n")

    return {
        "success": True,
        "exit_code": returncode,
        "stdout": _emit_result_text(id_, "stdout", stdout),
        "stderr": _emit_result_text(id_, "stderr", stderr),
    }


def _parse_request_payload(content: str) -> List[Dict[str, Any]]:
    """解析单个 <request> 标签内的 JSON-RPC 内容，返回请求列表。

    JSON 解析失败时返回带上下文的错误项。
    """
    blocks: List[Dict[str, Any]] = []
    try:
        parsed: Any = json.loads(content)
        if isinstance(parsed, list):
            for item in cast(List[Any], parsed):
                if isinstance(item, dict):
                    blocks.append(cast(Dict[str, Any], item))
                else:
                    blocks.append({"_parse_error": "请求必须是 JSON 对象"})
        elif isinstance(parsed, dict):
            blocks.append(cast(Dict[str, Any], parsed))
        else:
            blocks.append({"_parse_error": "请求必须是 JSON 对象"})
    except json.JSONDecodeError as e:
        # 构建带上下文的错误信息（不重复行号列号，只保留错误描述和上下文）
        pos = e.pos
        start = max(0, pos - 30)
        end = min(len(content), pos + 30)
        context_before = content[start:pos]
        # 取出错误位置的字符（若 pos 超出长度则用空格代替）
        error_char = content[pos] if pos < len(content) else " "
        context_after = content[pos + 1 : end]
        context_msg = f"{context_before}**{error_char}**{context_after}"
        if start > 0:
            context_msg = "..." + context_msg
        if end < len(content):
            context_msg = context_msg + "..."
        error_msg = f"JSON 解析失败：{e.msg}。附近内容：{context_msg}"
        blocks.append({"_parse_error": error_msg})
    return blocks


def _extract_chat2cli_fence_blocks(text: str) -> List[str]:
    """提取所有 chat2cli 围栏代码块的内容。

    开头与闭合围栏的反引号数量必须一致。当 data 块内容需要包含
    字面反引号围栏时，使用更长（四个或更多）的外层围栏，避免内容
    中的反引号围栏被误识别为外层围栏的闭合。
    """
    blocks: List[str] = []
    pattern = re.compile(r"(`{3,})chat2cli[ \t]*\n(.*?)\n\1", re.DOTALL)
    for match in pattern.finditer(text):
        content = match.group(2)
        if content is not None:
            blocks.append(content)
    return blocks


def _has_bare_request(text: str) -> bool:
    """检测文本中是否存在代码块外的裸 <request> 标签。

    先移除所有 ```chat2cli 代码块，然后在剩余文本中搜索 <request> 标签。
    """
    # 移除 chat2cli 代码块（包括标签内的全部内容），围栏长度与开头一致
    pattern = re.compile(r"(`{3,})chat2cli[ \t]*\n.*?\n\1", re.DOTALL)
    text_without_blocks = re.sub(pattern, "", text)
    # 检查剩余文本中是否包含 <request> 标签
    return bool(re.search(r"<(?:request)>", text_without_blocks, re.IGNORECASE))


def has_truncated_fence(text: str) -> bool:
    """检测是否存在未闭合或提前截断的 chat2cli 围栏。

    当输入包含 ```chat2cli 围栏开头，但完整围栏解析器
    _extract_chat2cli_fence_blocks 提取到的块都没有 <request> 时，
    很可能是因为 data 块内的字面反引号围栏被误当成外层围栏的闭合。
    此时应提示使用更长的外层围栏。
    """
    if not re.search(r"`{3,}chat2cli", text):
        return False
    blocks = _extract_chat2cli_fence_blocks(text)
    if not blocks:
        return True
    # 提取到块但没有任何 <request>，说明块被提前截断
    return all("<request>" not in block for block in blocks)


def _parse_chat2cli_content(content: str) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
    """解析单个 chat2cli 代码块内容，提取 data 标签和 request 标签。

    data 标签优先级高于 request：data 块内部的 <request>
    属于字面内容，不会被当作 RPC 请求解析。
    """
    data_map: Dict[str, str] = {}
    blocks: List[Dict[str, Any]] = []

    # 左侧 data 分支优先匹配，整个 data 块（含其中 request）被吞掉，
    # 因此其中的 request 不会作为独立 token 被提取。
    pattern = re.compile(
        r"<data\.([^>\s]+)>(.*?)</data\.\1>"
        r"|<request>\s*(.*?)</request>",
        re.DOTALL,
    )

    for match in pattern.finditer(content):
        if match.group(1) is not None:
            data_content = match.group(2)
            if data_content is not None:
                data_map[match.group(1)] = data_content
            continue

        content_raw = match.group(3)
        if content_raw is None:
            continue
        rpc_content = content_raw.strip()
        if not rpc_content:
            continue
        blocks.extend(_parse_request_payload(rpc_content))

    return data_map, blocks


def _scan_blocks(text: str) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
    """单次扫描文本：先提取 chat2cli 代码块，再在其中提取 data 和 request 标签。

    仅代码块内的标签会被识别；代码块之外的标签一律视为一般对话文本。
    """
    data_map: Dict[str, str] = {}
    blocks: List[Dict[str, Any]] = []

    for content in _extract_chat2cli_fence_blocks(text):
        d_map, rpc_blocks = _parse_chat2cli_content(content)
        data_map.update(d_map)
        blocks.extend(rpc_blocks)

    return data_map, blocks


def extract_data_blocks(text: str) -> Dict[str, str]:
    """提取 chat2cli 代码块中的 <data.{id}>...</data.{id}> 块，返回 id -> 内容 映射。

    仅识别 chat2cli 代码块内的标签；代码块外的同名标签视为一般文本。
    块内容原样保留，不做任何转义，也不剥离任何包裹。
    """
    data_map, _ = _scan_blocks(text)
    return data_map


def resolve_data_refs(node: Any, data_map: Dict[str, str]) -> Any:
    """递归替换 params 中的 {"id": "..."} 引用为数据块内容。

    仅当 dict 恰好只含一个 "id" 键且值能在 data_map 中找到时才替换，
    避免把带 id 字段的普通对象误判为引用。引用不存在的 id 直接报错。
    """
    if isinstance(node, dict):
        node_dict = cast(Dict[Any, Any], node)
        if set(node_dict.keys()) == {"id"}:
            ref_value = node_dict["id"]
            if not isinstance(ref_value, str):
                return node_dict
            if ref_value not in data_map:
                raise KeyError(f"未找到数据块 id：{ref_value}")
            return data_map[ref_value]
        return {k: resolve_data_refs(v, data_map) for k, v in node_dict.items()}
    if isinstance(node, list):
        node_list = cast(List[Any], node)
        return [resolve_data_refs(item, data_map) for item in node_list]
    return node


def extract_chat2cli_blocks(text: str) -> List[Dict[str, Any]]:
    """提取所有 chat2cli 代码块中的 <request> 标签并解析 JSON。

    代码块外的 request 标签视为一般文本；data 块内部的 request
    属于字面内容，会被跳过。
    """
    _, blocks = _scan_blocks(text)
    return blocks


def validate_request(req: Dict[str, Any]) -> Tuple[bool, str]:
    """校验单个 JSON-RPC 请求结构，返回 (是否合法, 错误消息)"""
    # 顶层只允许已知字段
    allowed_top = {"jsonrpc", "method", "params", "id"}
    unknown_top = set(req.keys()) - allowed_top
    if unknown_top:
        return False, f"顶层存在未知字段：{sorted(unknown_top)}"

    if "method" not in req:
        return False, "缺少 method 字段"
    method = req.get("method")
    if method not in ("str_replace_editor", "pwsh", "skill"):
        return False, f"未知 method：{method}"

    if "params" not in req or not isinstance(req.get("params"), dict):
        return False, "params 必须是对象"

    # 各 method 允许的 params key（不含 id，id 必须在顶层）
    allowed_params = {
        "str_replace_editor": {"command", "path", "file_text", "old_str", "new_str", "insert_line", "offset", "limit"},
        "pwsh": {"command"},
        "skill": {"name"},
    }
    allowed = allowed_params[method]
    unknown_params = set(req["params"].keys()) - allowed
    if unknown_params:
        hint = ""
        if "id" in unknown_params:
            hint = "注意：id 必须放在顶层，不能放在 params 内。"
        return False, f"params 中存在未知字段：{sorted(unknown_params)}，method={method} 允许的字段：{sorted(allowed)}。{hint}"

    return True, ""


def dispatch_request(
    req: Dict[str, Any], data_map: Dict[str, str]
) -> Optional[Tuple[Dict[str, Any], str]]:
    """分发执行单个请求。

    返回 (JSON-RPC response, 附加内容块)。
    JSON-RPC notification（没有 id）只执行方法，不返回响应。
    """
    has_id = "id" in req
    req_id: Any = req.get("id")
    method: Optional[str] = req.get("method")
    params: Optional[Dict[str, Any]] = req.get("params")

    logging.debug("--- 分发请求 ---")
    logging.debug(f"  method: {method}")
    logging.debug(f"  params: {json.dumps(params, ensure_ascii=False, default=str)}")
    logging.debug(f"  has_id: {has_id}, id: {req_id}")

    if "_parse_error" in req:
        # 始终输出错误信息到 stderr，不依赖 debug 模式
        sys.stderr.write(f"[chat2cli] JSON 解析错误: {req['_parse_error']}\n")
        sys.stderr.flush()
        logging.debug(f"  解析错误: {req['_parse_error']}")
        # 返回错误响应，id 取请求中的 id（可能为 None）
        return {
            "jsonrpc": "2.0",
            "error": {"code": -32700, "message": req["_parse_error"]},
            "id": req.get("id"),  # 可能为 None
        }, ""

    # 在校验前替换数据引用：{"id": "..."} 此时还是对象，校验无法识别
    if isinstance(req.get("params"), dict):
        try:
            resolved_params = resolve_data_refs(req["params"], data_map)
        except KeyError as e:
            if not has_id:
                return None
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32602, "message": str(e)},
                "id": req_id,
            }, ""
        req = {**req, "params": resolved_params}
        params = cast(Dict[str, Any], req.get("params"))

    valid, err_msg = validate_request(req)
    logging.debug(f"  校验结果: {'通过' if valid else '失败 - ' + err_msg}")
    if not valid:
        if not has_id:
            return None
        return {
            "jsonrpc": "2.0",
            "error": {"code": -32600, "message": err_msg},
            "id": req_id,
        }, ""

    method = cast(str, req["method"])
    params = cast(Dict[str, Any], req["params"])

    try:
        response: Optional[Dict[str, Any]] = None
        content_block = ""
        logging.debug(f"  执行 method: {method}")

        if method == "str_replace_editor":
            meta, content_block = execute_str_replace_editor(req_id, params)
            if meta.get("success"):
                for key in ("total_lines", "returned_lines", "first_line", "last_line", "message"):
                    meta.pop(key, None)
                response = {"jsonrpc": "2.0", "id": req_id, "result": meta}
                logging.debug(f"  执行结果: 成功 - {meta}")
            else:
                response = {
                    "jsonrpc": "2.0",
                    "error": {"code": -32000, "message": meta.get("message", "未知错误")},
                    "id": req_id,
                }
                logging.debug(f"  执行结果: 失败 - {meta.get('message', '未知错误')}")

        elif method == "pwsh":
            logging.debug(f"  执行 PowerShell 命令: {params.get('command', '')[:200]}...")
            result = execute_pwsh(req_id, params, data_map)
            if result.get("success"):
                response = {"jsonrpc": "2.0", "id": req_id, "result": result}
                logging.debug(f"  执行结果: 成功, exit_code={result.get('exit_code')}")
            else:
                response = {
                    "jsonrpc": "2.0",
                    "error": {"code": -32000, "message": result.get("message", "未知错误")},
                    "id": req_id,
                }
                logging.debug(f"  执行结果: 失败 - {result.get('message', '未知错误')}")

        elif method == "skill":
            logging.debug(f"  激活 skill: {params.get('name', '')}")
            meta, content_block = execute_skill(req_id, params)
            if meta.get("success"):
                meta.pop("message", None)
                response = {"jsonrpc": "2.0", "id": req_id, "result": meta}
                logging.debug(f"  执行结果: 成功 - skill '{meta.get('name')}' 已激活")
            else:
                response = {
                    "jsonrpc": "2.0",
                    "error": {"code": -32000, "message": meta.get("message", "未知错误")},
                    "id": req_id,
                }
                logging.debug(f"  执行结果: 失败 - {meta.get('message', '未知错误')}")

        if not has_id:
            logging.debug("  请求为 notification，不返回响应")
            return None

        if response is None:
            logging.debug("  响应为空")
            return None

        logging.debug(f"  响应已生成: id={response.get('id')}")
        return response, content_block

    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        logging.debug(f"  执行异常: {e}")
        if not has_id:
            return None
        return {
            "jsonrpc": "2.0",
            "error": {"code": -32603, "message": f"内部错误：{str(e)}"},
            "id": req_id,
        }, ""

def _write_stderr_summary(text: str, max_chars: int = 200) -> None:
    """输出 stderr 汇总，过长内容在展示层截断并提示。"""
    if len(text) <= max_chars:
        sys.stderr.write(text)
        return

    truncated = len(text) - max_chars
    sys.stderr.write(f"{text[:max_chars]} ({truncated} more chars)\n")


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="chat2cli 语言执行器")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="开启调试模式，回显输入、解析、提取和执行过程",
    )
    args = parser.parse_args()

    # 配置 logging
    log_level = logging.DEBUG if args.debug else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="[%(levelname)s] %(message)s",
        stream=sys.stderr,
    )

    # 重置带外数据全局状态，避免多次调用（如测试）串扰
    global _pending_oob_data
    _pending_oob_data.clear()

    # 读取 stdin 全部内容
    input_text = sys.stdin.read()
    logging.debug("=" * 60)
    logging.debug("【1. 原始输入】")
    if input_text:
        logging.debug(input_text)
    else:
        logging.debug("（空输入）")
    logging.debug("=" * 60)

    if not input_text.strip():
        sys.stderr.write("[chat2cli] 输入为空，已输出初始指令。\n")
        print_instruction()
        return

    logging.debug("【2. 提取 chat2cli 代码块】")
    data_map, requests = _scan_blocks(input_text)
    logging.debug(f"提取到 {len(data_map)} 个数据块: {sorted(data_map.keys())}")
    logging.debug(f"提取到 {len(requests)} 个请求")
    for i, req in enumerate(requests):
        req_preview = json.dumps(req, ensure_ascii=False, default=str, indent=2)
        logging.debug(f"  请求 #{i+1}:\n{req_preview}")
    logging.debug("=" * 60)

    if not requests:
        # 检测存在 chat2cli 围栏但未提取到 request 的情况，
        # 通常是 data 块内字面反引号围栏导致外层围栏被提前截断。
        # 需要优先于裸 request 检测，因为截断会让 request 落到代码块外。
        if has_truncated_fence(input_text):
            error_msg = (
                "错误：检测到 chat2cli 围栏代码块，但无法完整识别其中内容。\n"
                "如果 data 块内容包含字面的 ``` 围栏，请使用更长（四个或更多）\n"
                "反引号的外层围栏，例如：\n"
                "\n"
                "````chat2cli\n"
                "<data.code>\n"
                "```\n"
                "字面围栏内容\n"
                "```\n"
                "</data.code>\n"
                "<request>\n"
                '{"jsonrpc":"2.0","id":1,"method":"pwsh","params":{"command":"echo hello"}}\n'
                "</request>\n"
                "````\n"
            )
            print(error_msg)
            return

        # 检测是否有裸 request 标签（在 chat2cli 代码块外）
        if _has_bare_request(input_text):
            error_msg = (
                "错误：检测到 <request> 标签未包裹在 ```chat2cli 代码块中。\n"
                "请将 <request> 标签放在 ```chat2cli 代码块内，例如：\n"
                "\n"
                "```chat2cli\n"
                "<request>\n"
                '{"jsonrpc":"2.0","id":1,"method":"pwsh","params":{"command":"echo hello"}}\n'
                "</request>\n"
                "```\n"
            )
            print(error_msg)
            return

        sys.stderr.write("[chat2cli] 未检测到 chat2cli 代码块或 request 标签，已输出初始指令。\n")
        print_instruction()
        return

    responses: List[Dict[str, Any]] = []
    content_blocks: List[str] = []
    summary_parts: List[str] = []

    logging.debug("【3. 执行请求】")
    for idx, req in enumerate(requests):
        logging.debug(f"处理请求 #{idx+1}:")
        result = dispatch_request(req, data_map)
        if result is None:
            logging.debug(f"  请求 #{idx+1}: 无响应（notification 或空）")
            continue
        resp, content_block = result
        responses.append(resp)
        if content_block:
            content_blocks.append(content_block)
        # 构建 stderr 汇总
        if "error" in resp:
            summary_parts.append(f"id={resp.get('id')}: 失败 - {resp['error']['message']}")
            logging.debug(f"  请求 #{idx+1}: 响应错误 - {resp['error']['message']}")
        else:
            method: Any = req.get("method", "unknown")
            if method == "str_replace_editor":
                summary_parts.append(
                    f"str_replace_editor id={resp.get('id')}: 完成操作"
                )
                logging.debug(f"  请求 #{idx+1}: str_replace_editor 成功")
            elif method == "pwsh":
                params: Dict[str, Any] = cast(Dict[str, Any], req.get("params", {}))
                cmd = params.get("command", "")
                cmd_summary = cmd[:50] + "..." if len(cmd) > 50 else cmd
                summary_parts.append(f"pwsh id={resp.get('id')}: {cmd_summary}")
                logging.debug(f"  请求 #{idx+1}: pwsh 成功")
            elif method == "skill":
                summary_parts.append(f"skill id={resp.get('id')}: 已激活")
                logging.debug(f"  请求 #{idx+1}: skill 成功")
    logging.debug("=" * 60)

    # 输出 JSON-RPC 响应，统一包裹在 chat2cli 代码块中
    json_resp = (
        json.dumps(responses[0], ensure_ascii=False, indent=2)
        if len(responses) == 1
        else json.dumps(responses, ensure_ascii=False, indent=2)
    )
    print("```chat2cli")
    # 输出带外数据块（OOB 引用内容，按注册顺序）
    if _pending_oob_data:
        for ref_id, ref_content in _pending_oob_data.items():
            print(_data_block_text(ref_id, ref_content))
    # 输出附加内容块（view 结果）
    if content_blocks:
        print("\n".join(content_blocks))
    # 用 response 标签区分机器反馈
    print("<response>")
    print(json_resp)
    print("</response>")
    print("```")

    # stderr 汇总
    if summary_parts:
        for part in summary_parts:
            _write_stderr_summary(f"[chat2cli] {part}\n")
        _write_stderr_summary(f"[chat2cli] 共执行 {len(responses)} 个本地 RPC 调用。\n")


if __name__ == "__main__":
    main()
