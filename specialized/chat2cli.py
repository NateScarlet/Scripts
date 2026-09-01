#!/usr/bin/env python3
# pyright: strict

"""
chat2cli.py - JSON-RPC 工具调用助手（代码块标识已改为 tool）

从 stdin 读取文本，提取 ```tool 代码块，解析 JSON-RPC 2.0 请求，
执行本地操作（文件替换或 PowerShell 命令），并将结果以 JSON-RPC 2.0
响应格式输出到 stdout。输入为空或无 tool 代码块时，输出初始指令。

典型用法（PowerShell）:
    Get-Clipboard | python chat2cli.py | Set-Clipboard
"""

from __future__ import annotations

import os
import sys

# 设置 PYTHONIOENCODING，确保子 Python 进程也以 UTF-8 输出，
# 避免 Windows 控制台 GBK 代码页下出现中文乱码。
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
import re
import json
import subprocess
import threading
import difflib
import signal
from datetime import date
from typing import Any, Dict, List, Tuple, cast

# 确保输入输出使用 UTF-8（避免 Windows 默认编码问题）
try:
    sys.stdin.reconfigure(encoding="utf-8")  # type: ignore
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore
except AttributeError:
    pass


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

将所有工具调用放在一个 tool 代码块中。代码块内是 JSON-RPC 请求，
支持单个对象或对象数组（批处理，按顺序执行）。不支持 tool 以外的代码块语言标识。

回复时如需调用工具，请直接在正文中按以下 response_template 输出工具调用：

<response_template>
简短说明思路：
```tool
{{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "pwsh",
  "params": {{
    "command": "在此填写要执行的命令"
  }}
}}
```
</response_template>

代码块可以出现在正文的任意位置，也可以前后补充必要的说明文字，
但代码块本身必须完整地出现在正文回复中，工具调用才会被执行。

可用方法：

1. str_replace_editor - 自定义编辑工具（查看、创建、编辑文件）：
{{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "str_replace_editor",
  "params": {{
    "command": "view",
    "path": "文件或目录的绝对路径"
  }}
}}
- command 支持：view、create、str_replace、insert。
- path 必须是绝对路径，且只能指向当前工作目录内的文件或目录。
- view：查看文件（cat -n 效果）或目录（列出非隐藏项，最多 2 层）。
- create：创建新文件（path 已存在时报错）。
- str_replace：替换文件中的文本（old_str 需唯一匹配）。
- insert：在指定行后插入文本。
- 状态在多次调用间保持持久。
- 长输出会截断并标记 <response clipped>。

2. pwsh - 执行 PowerShell 命令：
{{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "pwsh",
  "params": {{
    "description": "命令用途简述（可选，用于汇总展示）",
    "command": "要执行的命令"
  }}
}}
- command 为通过 pwsh.exe 执行的命令，无超时限制（用户可通过 Ctrl+C 中断）。
- 仅支持非交互式命令。
- description 可选，用于执行汇总展示。

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

请根据用户需求，生成包含 JSON-RPC 请求的 tool 代码块。
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
    import difflib
    import sys

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

    abs_path = os.path.abspath(path)
    old_lines = old_normalized.split("\n")
    new_lines = new_normalized.split("\n")

    # 检查 old 和 new 是否相同
    if old_normalized == new_normalized:
        sys.stderr.write(f"\033[33m⚠️  str_replace: old 和 new 内容相同，文件未修改: {abs_path}\033[0m\n")
        sys.stderr.flush()
        return {
            "success": True,
            "path": abs_path,
            "deleted_lines": 0,
            "added_lines": 0,
            "message": f"文件未修改（old 和 new 相同）: {abs_path}",
        }

    new_content_normalized = content.replace(old_normalized, new_normalized, 1)
    new_content = _restore_newlines(new_content_normalized, newline_style)
    try:
        with open(path, "w", encoding=encoding_to_use, newline="") as f:
            f.write(new_content)
    except Exception as e:
        return {"success": False, "message": f"错误：写入文件失败：{str(e)}"}

    # 生成彩色 diff 输出到 stderr
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        lineterm=""
    )
    diff_output = list(diff)

    if diff_output:
        sys.stderr.write(f"\033[36m📝 str_replace 修改 {path}:\033[0m\n")
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

    # 计算实际行数变化
    deleted_lines = max(0, old_normalized.count("\n"))
    added_lines = max(0, new_normalized.count("\n"))

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
    import difflib
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
            f"[chat2cli] 请用户切换到对应目录（{os.path.dirname(path_raw)}）后再执行此工具。\n\n"
        )
        sys.stderr.flush()
        return {
            "success": False,
            "message": "错误：path 必须是绝对路径，且只能指向当前工作目录内的文件或目录。如需操作目录外的文件，请提示用户在对应目录下重新运行此工具。",
        }, ""

    if command == "view":
        if os.path.isdir(path):
            return _view_directory(id_, path)
        elif os.path.isfile(path):
            return _view_file(id_, path, params)
        else:
            return {"success": False, "message": f"错误：路径不存在：{path}"}, ""

    elif command == "create":
        if os.path.exists(path):
            return {"success": False, "message": f"错误：文件已存在：{path}"}, ""
        file_text = params.get("file_text")
        if not isinstance(file_text, str):
            return {"success": False, "message": "错误：create 命令需要 file_text 参数（字符串）。"}, ""
        try:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(file_text)
        except Exception as e:
            return {"success": False, "message": f"错误：创建文件失败：{str(e)}"}, ""
        return {
            "success": True,
            "path": os.path.abspath(path),
            "message": f"文件已创建：{os.path.abspath(path)}",
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


def _view_file(id_: Any, path: str, params: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
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
    meta = {
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

    content_block = f'<content id="{id_}">\n{meta["path"]}:L{first_line}-{last_line}\n{content_with_footer}\n</content>\n'
    return meta, content_block


def _view_directory(id_: Any, path: str) -> Tuple[Dict[str, Any], str]:
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
            except Exception:
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

    content_block = f'<content id="{id_}">\n{os.path.abspath(path)}\n' + "\n".join(lines) + "\n</content>\n"
    meta = {
        "success": True,
        "path": os.path.abspath(path),
        "entry_count": len(entries),
        "message": "Directory listed.",
    }
    return meta, content_block


def _str_replace_file(id_: Any, path: str, old_str: str, new_str: str) -> Dict[str, Any]:
    """替换文件中的文本，返回 result 字典"""
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
            "success": True,
            "path": abs_path,
            "deleted_lines": 0,
            "added_lines": 0,
            "message": f"文件未修改（old_str 和 new_str 相同）: {abs_path}",
        }

    new_content_normalized = content.replace(old_normalized, new_normalized, 1)
    new_content = _restore_newlines(new_content_normalized, newline_style)
    try:
        with open(path, "w", encoding=encoding_to_use, newline="") as f:
            f.write(new_content)
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

    deleted_lines = max(0, old_normalized.count("\n"))
    added_lines = max(0, new_normalized.count("\n"))
    return {
        "success": True,
        "path": abs_path,
        "deleted_lines": deleted_lines,
        "added_lines": added_lines,
        "message": f"The file {abs_path} has been updated successfully.",
    }


def _insert_in_file(id_: Any, path: str, insert_line: int, new_str: str) -> Dict[str, Any]:
    """在指定行后插入文本，返回 result 字典"""
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
    content_lines = content.split("\n")
    if content_lines and content_lines[-1] == "":
        content_lines = content_lines[:-1]

    if insert_line > len(content_lines):
        return {
            "success": False,
            "message": f"错误：insert_line={insert_line} 超出文件行数 {len(content_lines)}。",
        }

    new_str_normalized = _normalize_newlines(new_str)
    content_lines.insert(insert_line, new_str_normalized)
    new_content_normalized = "\n".join(content_lines)
    new_content = _restore_newlines(new_content_normalized, newline_style)

    try:
        with open(path, "w", encoding=encoding_to_use, newline="") as f:
            f.write(new_content)
    except Exception as e:
        return {"success": False, "message": f"错误：写入文件失败：{str(e)}"}

    abs_path = os.path.abspath(path)
    sys.stderr.write(f"\033[36m📝 str_replace_editor insert {path}: 在第 {insert_line} 行后插入\033[0m\n")
    sys.stderr.flush()
    return {
        "success": True,
        "path": abs_path,
        "inserted_line": insert_line + 1,
        "message": f"The file {abs_path} has been updated successfully.",
    }



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

    def _stream_reader(stream: Any, stream_name: str, lines_list: List[str]) -> None:
        """逐行读取子进程输出，实时写入 stderr 并累积到列表"""
        try:
            for line in iter(stream.readline, ""):
                sys.stderr.write(f"[pwsh:{stream_name}] {line}")
                sys.stderr.flush()
                lines_list.append(line)
        finally:
            try:
                stream.close()
            except Exception:
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
        except Exception:
            pass
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
        except Exception:
            proc.kill()
            proc.wait()
        raise
    finally:
        # 恢复原始信号处理器
        signal.signal(signal.SIGINT, original_handler)

    t_out.join(timeout=5)
    t_err.join(timeout=5)

    stdout = "".join(stdout_lines).rstrip("\n")
    stderr = "".join(stderr_lines).rstrip("\n")

    stdout_display, stderr_display = _truncate_output(id_, stdout, stderr)

    return {
        "success": True,
        "exit_code": returncode,
        "stdout": stdout_display,
        "stderr": stderr_display,
    }


def extract_chat2cli_blocks(text: str) -> List[Dict[str, Any]]:
    """提取所有 ```tool 代码块并解析 JSON"""
    blocks: List[Dict[str, Any]] = []
    pattern = re.compile(r"```tool\s*\n(.*?)\n```", re.DOTALL)
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
        "pwsh": {"command", "description"},
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
        if method == "str_replace_editor":
            meta, content_block = execute_str_replace_editor(req_id, params)
            if meta.get("success"):
                if content_block:
                    total_lines = meta.get("total_lines", 0)
                    first_line = meta.get("first_line", 0)
                    last_line = meta.get("last_line", 0)
                    meta.pop("total_lines", None)
                    meta.pop("returned_lines", None)
                    meta.pop("first_line", None)
                    meta.pop("last_line", None)
                    meta.pop("message", None)
                    return {"jsonrpc": "2.0", "result": meta, "id": req_id}, content_block
                else:
                    return {"jsonrpc": "2.0", "result": meta, "id": req_id}, ""
            else:
                return {
                    "jsonrpc": "2.0",
                    "error": {"code": -32000, "message": meta.get("message", "未知错误")},
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
        sys.stderr.write("[tool] 输入为空，已输出初始指令。\n")
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
            if method == "str_replace_editor":
                summary_parts.append(
                    f"str_replace_editor id={resp.get('id')}: 完成操作"
                )
            elif method == "pwsh":
                params: Dict[str, Any] = cast(Dict[str, Any], req.get("params", {}))
                desc: Any = params.get("description", "(无描述)")
                summary_parts.append(f"pwsh id={resp.get('id')}: {desc}")


    # 输出附加内容块（read 结果）
    if content_blocks:
        print("\n".join(content_blocks))

    # 输出 JSON-RPC 响应，包裹在 chat2cli 代码块中
    json_resp = (
        json.dumps(responses[0], ensure_ascii=False, indent=2)
        if len(responses) == 1
        else json.dumps(responses, ensure_ascii=False, indent=2)
    )
    print("```tool-result")
    print(json_resp)
    print("```")

    # stderr 汇总
    if summary_parts:
        for part in summary_parts:
            sys.stderr.write(f"[chat2cli] {part}\n")
        sys.stderr.write(f"[chat2cli] 共执行 {len(responses)} 个工具调用。\n")


if __name__ == "__main__":
    main()
