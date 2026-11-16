"""search_dsh_sessions 的回归测试。"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import zstandard as zstd

sys.path.insert(0, str(Path(__file__).parent))

from search_dsh_sessions import (
    Hit,
    SessionResult,
    render_results,
    search_workspace,
    workspace_dir_name,
)


def _make_session(root: Path, workspace: str, session_id: str, records: list[dict]) -> None:
    """在内存中构造一个最小可用的 zstd 压缩会话，避免依赖真实归档。"""
    session_dir = root / workspace_dir_name(Path(workspace)) / f"session-{session_id}"
    session_dir.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
    data = zstd.ZstdCompressor().compress(payload.encode("utf-8"))
    (session_dir / "session.v4.jsonl.zstd").write_bytes(data)


def _base_records(session_id: str, cwd: str, messages: list[tuple[str, str]]) -> list[dict]:
    records = [
        {
            "type": "session",
            "version": 4,
            "id": f"session-{session_id}",
            "createdAt": 1700000000000,
            "cwd": cwd,
        },
        {
            "type": "session/title",
            "seq": 1,
            "time": 1700000000001,
            "data": {"title": "测试会话标题"},
        },
    ]
    for seq, (role, text) in enumerate(messages, start=2):
        record_type = "user/message" if role == "user" else "assistant/message"
        records.append(
            {
                "type": record_type,
                "seq": seq,
                "time": 1700000000000 + seq,
                "data": {"content": [{"type": "text", "text": text}]},
            }
        )
    return records


def test_workspace_dir_name_matches_dsh_layout() -> None:
    assert workspace_dir_name(Path("C:\\Workspaces\\scripts")) == "--C-Workspaces-scripts--"
    assert workspace_dir_name(Path("C:\\Users\\me\\Documents\\a b")) == "--C-Users-me-Documents-a-b--"


def test_search_workspace_returns_only_sessions_with_literal_hit(tmp_path: Path) -> None:
    root = tmp_path / "sessions"
    workspace = str(tmp_path / "ws")

    _make_session(
        root,
        workspace,
        "aaaaaaaa-1111-1111-1111-111111111111",
        _base_records(
            "aaaaaaaa-1111-1111-1111-111111111111",
            workspace,
            [("user", "请帮我搜索 fooBar 这个字面词"), ("assistant", "没有相关内容")],
        ),
    )
    _make_session(
        root,
        workspace,
        "bbbbbbbb-2222-2222-2222-222222222222",
        _base_records(
            "bbbbbbbb-2222-2222-2222-222222222222",
            workspace,
            [("user", "完全不相关的内容")],
        ),
    )

    results = search_workspace(
        root / workspace_dir_name(Path(workspace)), "foobar", False, zstd.ZstdDecompressor()
    )

    assert len(results) == 1
    assert results[0].title == "测试会话标题"
    assert results[0].session_id == "session-aaaaaaaa-1111-1111-1111-111111111111"
    assert results[0].hits[0].positions == [6]  # fooBar 的下标，不区分大小写命中


def _tool_call(name: str, arguments: dict, seq: int) -> dict:
    return {
        "type": "tool/call",
        "seq": seq,
        "time": 1700000000000 + seq,
        "data": {
            "turn": 1,
            "step": seq,
            "callId": f"call_{seq}",
            "name": name,
            "arguments": json.dumps(arguments, ensure_ascii=False),
        },
    }


def test_search_workspace_finds_ask_user_question_arguments(tmp_path: Path) -> None:
    root = tmp_path / "sessions"
    workspace = str(tmp_path / "ws")
    session_id = "dddddddd-3333-3333-3333-333333333333"
    records = _base_records(session_id, workspace, [("user", "无关内容")])
    records.insert(
        1,
        _tool_call(
            "ask_user_question",
            {
                "questions": [
                    {
                        "id": "scope",
                        "header": "SID 选择",
                        "question": "放行外部目录时用哪个 SID 写 ACE？",
                        "options": [{"label": "复用现有 SID（推荐）"}],
                    }
                ]
            },
            2,
        ),
    )
    _make_session(root, workspace, session_id, records)

    results = search_workspace(
        root / workspace_dir_name(Path(workspace)),
        "放行外部目录时",
        False,
        zstd.ZstdDecompressor(),
    )

    assert len(results) == 1
    assert any("放行外部目录时" in hit.text for hit in results[0].hits)


def test_search_workspace_finds_any_tool_call_arguments(tmp_path: Path) -> None:
    root = tmp_path / "sessions"
    workspace = str(tmp_path / "ws")
    session_id = "eeeeeeee-4444-4444-4444-444444444444"
    records = _base_records(session_id, workspace, [])
    records.insert(1, _tool_call("write", {"file_path": "demo.py", "content": "UNIQUE_MARKER = 1\n"}, 2))
    _make_session(root, workspace, session_id, records)

    results = search_workspace(
        root / workspace_dir_name(Path(workspace)),
        "UNIQUE_MARKER",
        False,
        zstd.ZstdDecompressor(),
    )

    assert len(results) == 1


def test_render_results_highlights_term_and_keeps_context() -> None:
    result = SessionResult(
        session_id="session-cccc",
        title="高亮测试",
        cwd="C:\\Workspaces\\demo",
        created_ms=1700000000000,
        hits=[Hit(text="前缀 foobar 后缀", positions=[3])],
    )
    out = io.StringIO()

    render_results([result], "foobar", 3, out)
    rendered = out.getvalue()

    assert "高亮测试" in rendered
    assert "foobar" in rendered
    assert "\x1b[" in rendered  # 命中词被 ANSI 高亮
    assert "前缀" in rendered and "后缀" in rendered  # 上下文被保留
