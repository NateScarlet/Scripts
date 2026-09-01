#!/usr/bin/env python3
# pyright: strict

"""
chat2cli.py - JSON-RPC 工具调用助手

从 stdin 读取文本，提取 ```chat2cli 代码块，解析 JSON-RPC 2.0 请求，
执行本地操作（文件替换或 PowerShell 命令），并将结果以 JSON-RPC 2.0
响应格式输出到 stdout。输入为空或无 chat2cli 代码块时，输出初始指令。

典型用法（PowerShell）:
    Get-Clipboard | python chat2cli.py | Set-Clipboard
"""

from __future__ import annotations

import sys
import os
import re
import json
import subprocess
import difflib
from datetime import date
from typing import Any, Dict, List, Tuple, cast

# 确保输入输出使用 UTF-8（避免 Windows 默认编码问题）
try:
    sys.stdin.reconfigure(encoding="utf-8")  # type: ignore
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore
except AttributeError:
    pass

# 工具超时设置（秒）
COMMAND_TIMEOUT = 30

# 已发现的 skills 缓存（name -> 信息字典）
_discovered_skills: Dict[str, Dict[str, Any]] = {}


def _parse_skill_frontmatter(skill_md_path: str) -> Tuple[str, str]:
    """解析 SKILL.md 的 YAML frontmatter，返回 (name, description)"""
    try:
        with open(skill_md_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return "", ""

    # frontmatter 必须以 --- 开头
    if not content.startswith("---"):
        return "", ""

    end_idx = content.find("\n---", 3)
    if end_idx == -1:
        return "", ""

    frontmatter = content[3:end_idx].strip()
    name = ""
    description = ""
    in_description_block = False
    description_lines: List[str] = []

    for line in frontmatter.split("\n"):
        stripped = line.strip()
        if stripped.startswith("name:"):
            name = stripped[5:].strip().strip('"').strip("'")
        elif stripped.startswith("description:"):
            desc_value = stripped[12:].strip()
            if desc_value in ("|", ">"):
                # 多行 description 块
                in_description_block = True
                description_lines = []
            elif desc_value:
                description = desc_value.strip('"').strip("'")
        elif in_description_block:
            indent = len(line) - len(line.lstrip())
            if indent == 0 and stripped:
                # 无缩进的新字段，结束 description 块
                in_description_block = False
            else:
                description_lines.append(stripped)

    if in_description_block and description_lines:
        description = " ".join(description_lines)

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
        except Exception:
            continue

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


def _resolve_read_path(path: str) -> str:
    """解析 read 路径，支持合法相对路径和已发现 skill 目录下的绝对路径/~路径"""
    # 确保 skills 缓存已填充
    if not _discovered_skills:
        discover_skills()

    # 1. 合法相对路径直接返回
    if validate_path(path):
        return path

    # 2. 展开 ~ 并检查是否是 skill 目录下的文件
    expanded = os.path.expanduser(path)
    if os.path.isabs(expanded):
        abs_path = os.path.abspath(expanded)
        for skill_info in _discovered_skills.values():
            skill_dir = os.path.abspath(skill_info["path"])
            if abs_path == skill_dir or abs_path.startswith(skill_dir + os.sep):
                return abs_path

    return ""


def print_instruction():
    """输出初始系统环境提示词，用于指导模型调用工具"""
    cwd = os.getcwd()
    instruction = f"""<chat2cli_instruction>
你是一个能够调用本地工具的助手。你可以使用 JSON-RPC 2.0 格式调用工具。

将所有工具调用放在一个 ```chat2cli 代码块中。代码块内是 JSON-RPC 请求，
支持单个对象或对象数组（批处理，按顺序执行）。不支持 chat2cli 以外的代码块语言标识。

可用方法：

1. str_replace - 文件替换：
{{
  "jsonrpc": "2.0",
  "method": "str_replace",
  "params": {{
    "path": "相对路径",
    "old": "要替换的原文",
    "new": "新文本"
  }},
  "id": 1
}}
- path 必须是当前目录下的相对路径（禁止使用 .. 或绝对路径）。
- old 必须在文件中唯一匹配（出现且仅出现一次），否则会报错。
- old 不能为空字符串。
- 替换会直接写入原文件，不保留备份。

2. pwsh - 执行 PowerShell 命令：
{{
  "jsonrpc": "2.0",
  "method": "pwsh",
  "params": {{
    "description": "命令用途简述（可选，用于汇总展示）",
    "command": "要执行的命令"
  }},
  "id": 2
}}
- command 为通过 pwsh.exe 执行的命令，超时时间 {COMMAND_TIMEOUT} 秒。
- 仅支持非交互式命令。
- description 可选，用于执行汇总展示。

3. read - 读取文本文件：
{{
  "jsonrpc": "2.0",
  "method": "read",
  "params": {{
    "file_path": "相对路径或 skill 目录下文件路径",
    "offset": 1,
    "limit": 2000
  }},
  "id": 3
}}
- file_path 可为当前目录下的相对路径（禁止使用 ..），或已发现 skill 目录下的文件路径（支持绝对路径或 ~ 开头路径）。
- offset 为返回的起始行号（1 起，默认 1）。
- limit 为最大返回行数（默认 2000）。
- 返回内容以行号前缀形式输出（如 "123:content"），不做 JSON 转义。

4. skill - 激活指定 skill：
{{
  "jsonrpc": "2.0",
  "method": "skill",
  "params": {{
    "name": "skill 名称"
  }},
  "id": 4
}}
- name 必须是 available_skills 中列出的精确名称。
- 激活后返回 <skill_content> 块，包含该 skill 的完整指令。
- 仅在用户点名 skill，或任务明显匹配 skill 描述时调用，且每个 skill 只激活一次。

当前工作目录：{cwd}

请根据用户需求，生成包含 JSON-RPC 请求的 chat2cli 代码块。
</chat2cli_instruction>"""
    print(instruction)

    # 检查并输出 system-reminder（若存在 AGENTS 文件）
    reminder_parts: List[str] = []
    home_agents = os.path.expanduser("~/.chat2cli/AGENTS.md")
    if os.path.isfile(home_agents):
        try:
            with open(home_agents, "r", encoding="utf-8") as f:
                content = f.read()
            reminder_parts.append(
                f"Instructions from: ~/.chat2cli/AGENTS.md\n{content}"
            )
        except Exception:
            pass

    cwd_agents = os.path.join(cwd, "AGENTS.md")
    if os.path.isfile(cwd_agents):
        try:
            with open(cwd_agents, "r", encoding="utf-8") as f:
                content = f.read()
            reminder_parts.append(f"Instructions from: AGENTS.md\n{content}")
        except Exception:
            pass

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

If the user names a skill, or the task clearly matches a skill's description, call the `skill` tool with the exact skill name before taking task actions. Load all applicable skills, then follow their full instructions. This catalog contains summaries only; do not infer or follow a skill's instructions until it has been loaded.
A user may also invoke a skill directly; its <skill_content> block then appears in this conversation. Follow it, and do not call the `skill` tool again for that skill.
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


def execute_str_replace(id_: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    """执行文件替换，返回 JSON-RPC result 字典"""
    path = params.get("path")
    old = params.get("old")
    new = params.get("new")

    if not isinstance(path, str) or not validate_path(path):
        return {
            "success": False,
            "message": "错误：路径不合法。路径必须为当前目录下的相对路径，不能包含 .. 或绝对路径。",
        }
    if not isinstance(old, str) or not old:
        return {"success": False, "message": "错误：old 字符串不能为空。"}
    if not isinstance(new, str):
        return {"success": False, "message": "错误：new 必须是字符串。"}
    if not os.path.isfile(path):
        return {"success": False, "message": "错误：文件不存在。"}

    # 尝试以 UTF-8 读取，失败则回退到系统默认编码
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
            return {"success": False, "message": f"错误：读取文件失败：{str(e)}"}
    except Exception as e:
        return {"success": False, "message": f"错误：读取文件失败：{str(e)}"}

    newline_style = _detect_dominant_newline(raw_content)
    content = _normalize_newlines(raw_content)
    old_normalized = _normalize_newlines(old)
    new_normalized = _normalize_newlines(new)

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
            "message": f"错误：检测到 {count} 处匹配，无法唯一确定替换位置。请提供更长的 old 字符串。",
        }

    new_content_normalized = content.replace(old_normalized, new_normalized, 1)
    new_content = _restore_newlines(new_content_normalized, newline_style)
    try:
        with open(path, "w", encoding=encoding_to_use, newline="") as f:
            f.write(new_content)
    except Exception as e:
        return {"success": False, "message": f"错误：写入文件失败：{str(e)}"}

    abs_path = os.path.abspath(path)
    deleted_lines = old_normalized.count("\n")
    added_lines = new_normalized.count("\n")
    return {
        "success": True,
        "path": abs_path,
        "deleted_lines": deleted_lines,
        "added_lines": added_lines,
        "message": f"The file {abs_path} has been updated successfully.",
    }


def execute_read(id_: Any, params: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    """读取文件内容，返回 (元数据, 行号化内容)"""
    path_raw = params.get("file_path")
    if not isinstance(path_raw, str):
        return {
            "success": False,
            "message": "错误：路径不合法。路径必须为当前目录下的相对路径，不能包含 .. 或绝对路径。",
        }, ""
    path = _resolve_read_path(path_raw)
    if not path:
        return {
            "success": False,
            "message": "错误：路径不合法。路径必须为当前目录下的相对路径，或已发现 skill 目录下的文件路径。",
        }, ""
    if not os.path.isfile(path):
        return {"success": False, "message": "错误：文件不存在。"}, ""

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
    meta = {
        "success": True,
        "path": os.path.abspath(path),
        "total_lines": total_lines,
        "returned_lines": len(selected),
        "first_line": first_line,
        "last_line": last_line,
        "message": "Read completed.",
    }
    return meta, content_out


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


def _truncate_output(
    id_: Any,
    stdout: str,
    stderr: str,
    max_lines: int = 200,
) -> Tuple[str, str]:
    """对过长输出进行截断，完整内容写入 scratch 文件。"""

    def _process(stream_name: str, text: str) -> str:
        if not text:
            return text
        line_count = text.count("\n") + 1
        if line_count <= max_lines:
            return text

        scratch_dir = os.path.join(
            os.getcwd(), ".scratch", f"{date.today().isoformat()}-chat2cli"
        )
        try:
            os.makedirs(scratch_dir, exist_ok=True)
            safe_id = re.sub(r"[^\w\-.]", "_", str(id_))
            base_name = f"{safe_id}-{stream_name}"
            filepath = os.path.join(scratch_dir, f"{base_name}.txt")
            counter = 1
            while os.path.exists(filepath):
                filepath = os.path.join(scratch_dir, f"{base_name}_{counter}.txt")
                counter += 1
            with open(filepath, "w", encoding="utf-8", newline="") as f:
                f.write(text)
            rel_path = os.path.relpath(filepath, os.getcwd())
        except Exception:
            return text

        lines_list = text.split("\n")
        head = "\n".join(lines_list[:100])
        tail = "\n".join(lines_list[-100:])
        truncated = (
            f"{head}\n...[截断 {line_count - 200} 行]...\n{tail}\n"
            f"[完整输出已保存至: {rel_path}]"
        )
        return truncated

    stdout_display = _process("stdout", stdout)
    stderr_display = _process("stderr", stderr)
    return stdout_display, stderr_display


def execute_pwsh(id_: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    """执行 PowerShell 命令，返回 JSON-RPC result 字典"""
    command = params.get("command")

    if not isinstance(command, str) or not command.strip():
        return {"success": False, "message": "错误：command 不能为空。"}

    wrapped_command = (
        f"try {{ $PSStyle.OutputRendering = 'PlainText' }} catch {{}}; "
        f"[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; {command}"
    )
    try:
        # 为子进程补充 CI 环境变量：执行者始终是 agent，无交互终端，
        # CI=true 让 vitest 等工具默认进入非交互模式而非 watch，避免超时；
        # NO_COLOR=1 禁用彩色输出，避免转义码污染捕获的文本。
        env = os.environ.copy()
        env["CI"] = "true"
        env["NO_COLOR"] = "1"

        result = subprocess.run(
            ["pwsh.exe", "-NoProfile", "-Command", wrapped_command],
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            env=env,
        )
    except FileNotFoundError:
        return {
            "success": False,
            "message": "错误：未找到 pwsh.exe，请确保 PowerShell Core 已安装并添加到 PATH。",
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": f"错误：命令执行超时（超过 {COMMAND_TIMEOUT} 秒），已终止。",
        }
    except Exception as e:
        return {"success": False, "message": f"错误：命令执行异常：{str(e)}"}

    stdout = result.stdout.rstrip("\n")
    stderr = result.stderr.rstrip("\n")

    stdout_display, stderr_display = _truncate_output(id_, stdout, stderr)

    return {
        "success": True,
        "exit_code": result.returncode,
        "stdout": stdout_display,
        "stderr": stderr_display,
    }


def extract_chat2cli_blocks(text: str) -> List[Dict[str, Any]]:
    """提取所有 ```chat2cli 代码块并解析 JSON"""
    blocks: List[Dict[str, Any]] = []
    pattern = re.compile(r"```chat2cli\s*\n(.*?)\n```", re.DOTALL)
    for match in pattern.finditer(text):
        content = match.group(1).strip()
        if not content:
            continue
        try:
            parsed: Any = json.loads(content)
            if isinstance(parsed, list):
                item_list: List[Any] = cast(List[Any], parsed)
                for item in item_list:
                    if isinstance(item, dict):
                        blocks.append(cast(Dict[str, Any], item))
                    else:
                        blocks.append({"_parse_error": "请求必须是 JSON 对象"})
            elif isinstance(parsed, dict):
                blocks.append(cast(Dict[str, Any], parsed))
            else:
                blocks.append({"_parse_error": "请求必须是 JSON 对象"})
        except json.JSONDecodeError as e:
            blocks.append({"_parse_error": f"JSON 解析失败：{e}"})
    return blocks


def validate_request(req: Dict[str, Any]) -> Tuple[bool, str]:
    """校验单个 JSON-RPC 请求结构，返回 (是否合法, 错误消息)"""
    if "method" not in req:
        return False, "缺少 method 字段"
    method = req.get("method")
    if method not in ("str_replace", "pwsh", "read", "skill"):
        return False, f"未知 method：{method}"
    if "params" not in req or not isinstance(req.get("params"), dict):
        return False, "params 必须是对象"
    return True, ""


def dispatch_request(req: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    """分发执行单个请求，返回 (JSON-RPC 响应, 附加内容块)"""
    req_id: Any = req.get("id")

    if "_parse_error" in req:
        return {
            "jsonrpc": "2.0",
            "error": {"code": -32700, "message": req["_parse_error"]},
            "id": None,
        }, ""

    valid, err_msg = validate_request(req)
    if not valid:
        return {
            "jsonrpc": "2.0",
            "error": {"code": -32600, "message": err_msg},
            "id": req_id,
        }, ""

    method: Any = req["method"]
    params: Any = req["params"]

    try:
        if method == "str_replace":
            result = execute_str_replace(req_id, params)
            if result.get("success"):
                return {"jsonrpc": "2.0", "result": result, "id": req_id}, ""
            else:
                return {
                    "jsonrpc": "2.0",
                    "error": {"code": -32000, "message": result.get("message", "未知错误")},
                    "id": req_id,
                }, ""
        elif method == "pwsh":
            result = execute_pwsh(req_id, params)
            if result.get("success"):
                return {"jsonrpc": "2.0", "result": result, "id": req_id}, ""
            else:
                return {
                    "jsonrpc": "2.0",
                    "error": {"code": -32000, "message": result.get("message", "未知错误")},
                    "id": req_id,
                }, ""
        elif method == "skill":
            meta, content_block = execute_skill(req_id, params)
            if meta.get("success"):
                meta.pop("message", None)
                return {"jsonrpc": "2.0", "result": meta, "id": req_id}, content_block
            else:
                return {
                    "jsonrpc": "2.0",
                    "error": {"code": -32000, "message": meta.get("message", "未知错误")},
                    "id": req_id,
                }, ""
        else:  # read
            meta, content = execute_read(req_id, params)
            if meta.get("success"):
                total_lines = meta.get("total_lines", 0)
                if content:
                    content_with_footer = content + f"\n(End of file - total {total_lines} lines)"
                else:
                    content_with_footer = f"(End of file - total {total_lines} lines)"
                content_block = f'<chat2cli_content id="{req_id}">\n{content_with_footer}\n</chat2cli_content>\n'
                meta.pop("total_lines", None)
                meta.pop("returned_lines", None)
                meta.pop("first_line", None)
                meta.pop("last_line", None)
                meta.pop("message", None)
                return {"jsonrpc": "2.0", "result": meta, "id": req_id}, content_block
            else:
                return {
                    "jsonrpc": "2.0",
                    "error": {"code": -32000, "message": meta.get("message", "未知错误")},
                    "id": req_id,
                }, ""
    except Exception as e:
        return {
            "jsonrpc": "2.0",
            "error": {"code": -32603, "message": f"内部错误：{str(e)}"},
            "id": req_id,
        }, ""


def main():
    # 读取 stdin 全部内容
    input_text = sys.stdin.read()

    if not input_text.strip():
        sys.stderr.write("[chat2cli] 输入为空，已输出初始指令。\n")
        print_instruction()
        return

    requests = extract_chat2cli_blocks(input_text)
    if not requests:
        sys.stderr.write("[chat2cli] 未检测到 chat2cli 代码块，已输出初始指令。\n")
        print_instruction()
        return

    responses: List[Dict[str, Any]] = []
    content_blocks: List[str] = []
    summary_parts: List[str] = []
    for req in requests:
        resp, content_block = dispatch_request(req)
        responses.append(resp)
        if content_block:
            content_blocks.append(content_block)
        # 构建 stderr 汇总
        if "error" in resp:
            summary_parts.append(f"id={resp.get('id')}: 失败 - {resp['error']['message'][:50]}")
        else:
            result: Any = resp.get("result", {})
            method: Any = req.get("method", "unknown")
            if method == "str_replace":
                summary_parts.append(
                    f"str_replace id={resp.get('id')}: 删除{result.get('deleted_lines', 0)}行 新增{result.get('added_lines', 0)}行"
                )
            elif method == "pwsh":
                params: Dict[str, Any] = cast(Dict[str, Any], req.get("params", {}))
                desc: Any = params.get("description", "(无描述)")
                summary_parts.append(f"pwsh id={resp.get('id')}: {desc}")
            elif method == "read":
                summary_parts.append(f"read id={resp.get('id')}: 成功读取 {result.get('path', '')}")

    # 输出附加内容块（read 结果）
    if content_blocks:
        print("\n".join(content_blocks))

    # 输出 JSON-RPC 响应，包裹在 chat2cli 代码块中
    json_resp = (
        json.dumps(responses[0], ensure_ascii=False, indent=2)
        if len(responses) == 1
        else json.dumps(responses, ensure_ascii=False, indent=2)
    )
    print("```chat2cli-response")
    print(json_resp)
    print("```")

    # stderr 汇总
    if summary_parts:
        for part in summary_parts:
            sys.stderr.write(f"[chat2cli] {part}\n")
        sys.stderr.write(f"[chat2cli] 共执行 {len(responses)} 个工具调用。\n")


if __name__ == "__main__":
    main()
