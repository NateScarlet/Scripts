#!/usr/bin/env python3
"""按字面子串搜索 ~/.dsh/sessions 中某个工作区的会话，并高亮命中上下文。

会话归档是 zstd 压缩的 JSONL；本脚本只读取目标工作区对应的会话目录，
以流式方式解压，避免扫描全部工作区。命中结果直接写到 stdout。
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, TextIO

try:
    import zstandard as zstd
except ImportError:
    # 快速失败：依赖缺失时给出可执行的反馈，而不是降级到无法保证正确性的路径。
    raise SystemExit("缺少依赖 zstandard，请先安装：python -m pip install zstandard")

DEFAULT_SESSIONS_ROOT = Path.home() / ".dsh" / "sessions"
HIGHLIGHT = "\x1b[1;33m"
RESET = "\x1b[0m"
SEARCHABLE_TYPES = {"user/message", "assistant/message", "tool/result", "tool/call"}
SESSION_FILE_GLOB = "session-*/session.v*.jsonl.zstd"


@dataclass
class Hit:
    """一段文本及其中的命中位置。"""

    text: str
    positions: list[int]


@dataclass
class SessionResult:
    session_id: str
    title: str
    cwd: str
    created_ms: int
    hits: list[Hit]


def workspace_dir_name(workspace: Path | str) -> str:
    """按 DSH 规则把工作区绝对路径映射为会话目录名。"""
    normalized = str(workspace).replace(":", "")
    normalized = re.sub(r"[^0-9A-Za-z._-]", "-", normalized)
    return f"--{normalized}--"


def resolve_workspace_dir(workspace: str | None, sessions_root: Path) -> Path:
    """从给定目录（默认当前目录）向上寻找最近的会话目录。"""
    if not sessions_root.is_dir():
        raise SystemExit(f"会话根目录不存在: {sessions_root}")

    candidate = Path(workspace).expanduser() if workspace else Path.cwd()
    candidate = candidate.resolve()

    current = candidate
    while True:
        session_dir = sessions_root / workspace_dir_name(current)
        if session_dir.is_dir():
            return session_dir
        parent = current.parent
        if parent == current:
            break
        current = parent

    available = "\n  ".join(sorted(p.name for p in sessions_root.iterdir() if p.is_dir()))
    raise SystemExit(f"找不到工作区 {candidate} 对应的会话目录。可选工作区：\n  {available}")


def _iter_records(path: Path, dctx: zstd.ZstdDecompressor) -> Iterator[dict]:
    """流式解压并逐行解析 JSONL。"""
    with path.open("rb") as raw:
        with dctx.stream_reader(raw) as reader:
            with io.TextIOWrapper(reader, encoding="utf-8", errors="replace") as text:
                for line in text:
                    line = line.strip()
                    if not line:
                        continue
                    record = json.loads(line)
                    if isinstance(record, dict):
                        yield record


def _find_positions(text: str, pattern: str, case_sensitive: bool) -> list[int]:
    """返回字面子串的所有出现位置（不重叠）。"""
    hay = text if case_sensitive else text.lower()
    needle = pattern if case_sensitive else pattern.lower()
    positions: list[int] = []
    start = 0
    while True:
        index = hay.find(needle, start)
        if index < 0:
            break
        positions.append(index)
        start = index + len(needle)
    return positions


def _walk_strings(value: object) -> Iterator[str]:
    """递归取出 JSON 值中的非空字符串。"""
    if isinstance(value, str):
        if value:
            yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_strings(item)


def _extract_texts(record: dict) -> list[str]:
    """从消息、工具结果与工具调用参数中取出可搜索的文本块。

    用户消息的文本在 data.content，助手消息与工具结果的在 data.message.content；
    工具调用的参数是 JSON 字符串（data.arguments），取其中的字符串值。
    """
    record_type = record.get("type")
    if record_type not in SEARCHABLE_TYPES:
        return []
    data = record.get("data")
    if not isinstance(data, dict):
        return []

    if record_type == "tool/call":
        arguments = data.get("arguments")
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                return [arguments]  # 外部数据可能不是合法 JSON，退化为按原文搜索
        return list(_walk_strings(arguments))

    content = data.get("content")
    if not isinstance(content, list):
        message = data.get("message")
        content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list):
        return []
    return [
        block["text"]
        for block in content
        if isinstance(block, dict)
        and block.get("type") == "text"
        and isinstance(block.get("text"), str)
        and block["text"]
    ]


def search_session_file(
    path: Path, pattern: str, case_sensitive: bool, dctx: zstd.ZstdDecompressor
) -> SessionResult | None:
    """搜索单个会话文件，无命中返回 None。"""
    session_id = path.parent.name
    title = ""
    cwd = ""
    created_ms = 0
    hits: list[Hit] = []

    for record in _iter_records(path, dctx):
        record_type = record.get("type")
        if record_type == "session":
            session_id = record.get("id", session_id)
            cwd = record.get("cwd", "")
            created_ms = record.get("createdAt", 0)
        elif record_type == "session/title":
            data = record.get("data")
            if isinstance(data, dict) and isinstance(data.get("title"), str):
                title = data["title"]
        elif record_type in SEARCHABLE_TYPES:
            for text in _extract_texts(record):
                positions = _find_positions(text, pattern, case_sensitive)
                if positions:
                    hits.append(Hit(text=text, positions=positions))

    if not hits:
        return None
    return SessionResult(session_id, title or session_id, cwd, created_ms, hits)


def search_workspace(
    workspace_dir: Path, pattern: str, case_sensitive: bool, dctx: zstd.ZstdDecompressor
) -> list[SessionResult]:
    """搜索工作区目录下所有会话，按创建时间倒序返回有命中的会话。"""
    results: list[SessionResult] = []
    for path in sorted(workspace_dir.glob(SESSION_FILE_GLOB)):
        result = search_session_file(path, pattern, case_sensitive, dctx)
        if result is not None:
            results.append(result)
    results.sort(key=lambda item: item.created_ms, reverse=True)
    return results


def _merged_windows(
    positions: list[int], pattern_len: int, before: int, after: int, text_len: int
) -> list[tuple[int, int]]:
    """合并相邻的命中上下文窗口，避免重复输出重叠片段。"""
    windows: list[tuple[int, int]] = []
    for pos in positions:
        start = max(0, pos - before)
        end = min(text_len, pos + pattern_len + after)
        if windows and start <= windows[-1][1]:
            windows[-1] = (windows[-1][0], max(windows[-1][1], end))
        else:
            windows.append((start, end))
    return windows


def _highlight(text: str, positions: list[int], pattern_len: int) -> str:
    """用 ANSI 序列高亮命中词。"""
    parts: list[str] = []
    last = 0
    for pos in positions:
        parts.append(text[last:pos])
        parts.append(HIGHLIGHT + text[pos : pos + pattern_len] + RESET)
        last = pos + pattern_len
    parts.append(text[last:])
    return "".join(parts)


def render_results(results: list[SessionResult], pattern: str, context: int, out: TextIO) -> None:
    """把命中结果渲染到指定输出流（默认 stdout）。"""
    pattern_len = len(pattern)
    for result in results:
        when = (
            datetime.fromtimestamp(result.created_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")
            if result.created_ms
            else "未知时间"
        )
        total = sum(len(hit.positions) for hit in result.hits)
        out.write(f"会话: {result.title}  [{result.session_id}]\n")
        out.write(f"工作区: {result.cwd}   时间: {when}   命中: {total} 处\n")
        for hit in result.hits:
            for start, end in _merged_windows(
                hit.positions, pattern_len, context, context, len(hit.text)
            ):
                prefix = "…" if start > 0 else ""
                suffix = "…" if end < len(hit.text) else ""
                local_positions = [
                    pos - start for pos in hit.positions if start <= pos <= end - pattern_len
                ]
                fragment = _highlight(hit.text[start:end], local_positions, pattern_len)
                fragment = re.sub(r"[\r\n\t]+", " ", fragment)
                out.write(f"  {prefix}{fragment}{suffix}\n")
        out.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="按字面子串搜索 DSH 会话并高亮命中上下文（结果输出到 stdout）"
    )
    parser.add_argument("pattern", help="要搜索的字面词，不解析为正则")
    parser.add_argument("workspace", nargs="?", help="工作区目录，默认取当前目录对应的工作区")
    parser.add_argument(
        "-c", "--context", type=int, default=80, help="命中词前后保留的字符数（默认 80）"
    )
    parser.add_argument(
        "--case-sensitive", action="store_true", help="区分大小写（默认不区分大小写）"
    )
    parser.add_argument(
        "--sessions-root", type=Path, default=DEFAULT_SESSIONS_ROOT, help="会话根目录"
    )
    args = parser.parse_args(argv)

    sessions_root = args.sessions_root.expanduser()
    workspace_dir = resolve_workspace_dir(args.workspace, sessions_root)
    dctx = zstd.ZstdDecompressor()
    results = search_workspace(workspace_dir, args.pattern, args.case_sensitive, dctx)

    if not results:
        print(f"未找到匹配: {args.pattern}（工作区: {workspace_dir.name}）")
        return 0

    render_results(results, args.pattern, args.context, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
