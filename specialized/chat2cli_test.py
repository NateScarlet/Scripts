"""chat2cli.py 的提取逻辑单元测试。

重点覆盖：仅在 ```chat2cli 代码块内识别 <data.xxx> 和 <request> 标签；
代码块外的同名标签一律视为一般对话文本。
data 块内部的 <request> 属于字面内容，不应被当作 RPC 请求执行。
"""
import os
import tempfile
import unittest
from pathlib import Path

import chat2cli

# 缩进字符从实现常量取，换缩进字符后测试无需修改
IND = chat2cli._INSTRUCTION_INDENT


class TestExtractDataBlocks(unittest.TestCase):
    def test_simple(self):
        text = "```chat2cli\n<data.a>hello</data.a>\n```"
        self.assertEqual(chat2cli.extract_data_blocks(text), {"a": "hello"})

    def test_multiline(self):
        text = "```chat2cli\n<data.code>\nline1\nline2\n</data.code>\n```"
        self.assertEqual(
            chat2cli.extract_data_blocks(text), {"code": "\nline1\nline2\n"}
        )

    def test_ignores_data_outside_chat2cli_block(self):
        text = (
            "<data.a>hello</data.a>\n"
            "```chat2cli\n"
            "<request>\n"
            '{"jsonrpc":"2.0","id":1,"method":"skill","params":{"name":"x"}}\n'
            "</request>\n"
            "```"
        )
        self.assertEqual(chat2cli.extract_data_blocks(text), {})


class TestExtractChat2cliBlocks(unittest.TestCase):
    def test_normal_block(self):
        text = (
            "```chat2cli\n"
            "<request>\n"
            '{"jsonrpc":"2.0","id":1,"method":"skill","params":{"name":"x"}}\n'
            "</request>\n"
            "```"
        )
        blocks = chat2cli.extract_chat2cli_blocks(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["method"], "skill")

    def test_skips_request_inside_data_block(self):
        text = (
            "```chat2cli\n"
            "<data.example>\n"
            '<request>\n{"method":"pwsh"}\n</request>\n'
            "</data.example>\n"
            '<request>\n{"method":"skill"}\n</request>\n'
            "```"
        )
        blocks = chat2cli.extract_chat2cli_blocks(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["method"], "skill")

    def test_update_initial_example_scenario(self):
        # data 块内容包含完整 request 示例，字面内容不应被当作请求执行
        text = (
            "```chat2cli\n"
            "<data.example>\n"
            "<request>\n"
            '{"jsonrpc":"2.0","id":1,"method":"pwsh",'
            '"params":{"command":"Write-Output hi"}}\n'
            "</request>\n"
            "</data.example>\n"
            "```"
        )
        blocks = chat2cli.extract_chat2cli_blocks(text)
        self.assertEqual(blocks, [])

    def test_data_block_can_contain_literal_fence(self):
        # data 块内容包含字面的 ``` 围栏时，通过缩进避免误识别
        text = (
            "```chat2cli\n"
            f"{IND}<data.code>\n"
            f"{IND}```\n"
            f"{IND}literal fence content\n"
            f"{IND}```\n"
            f"{IND}</data.code>\n"
            f'{IND}<request>\n{IND}{{"method":"skill"}}\n{IND}</request>\n'
            "```"
        )
        blocks = chat2cli.extract_chat2cli_blocks(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["method"], "skill")
        data = chat2cli.extract_data_blocks(text)
        self.assertEqual(data["code"], "\n```\nliteral fence content\n```\n")

    def test_line_missing_indent_raises_error(self):
        # 后续行没有缩进字符开头时，视为非法输入
        text = (
            "```chat2cli\n"
            f"{IND}<request>\n"
            '{"method":"skill"}\n'
            f"{IND}</request>\n"
            "```"
        )
        with self.assertRaises(ValueError):
            chat2cli.extract_chat2cli_blocks(text)

    def test_unindented_block_uses_empty_prefix(self):
        # 首行无缩进时，内容原样返回
        text = (
            "```chat2cli\n"
            '<request>\n{"method":"skill"}\n</request>\n'
            "```"
        )
        blocks = chat2cli.extract_chat2cli_blocks(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["method"], "skill")

    def test_doubled_indent_produces_literal_char(self):
        # 缩进只移除一个字符，重复缩进行剥掉后保留一个字面缩进字符
        text = (
            "```chat2cli\n"
            f"{IND}<data.code>\n"
            f"{IND}{IND}literal\n"
            f"{IND}</data.code>\n"
            "```"
        )
        data = chat2cli.extract_data_blocks(text)
        self.assertEqual(data["code"], f"\n{IND}literal\n")

    def test_ignores_request_outside_chat2cli_block(self):
        text = (
            "<request>\n"
            '{"method":"pwsh"}\n'
            "</request>\n"
            "```chat2cli\n"
            '<request>\n{"method":"skill"}\n</request>\n'
            "```"
        )
        blocks = chat2cli.extract_chat2cli_blocks(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["method"], "skill")



class TestHasTruncatedFence(unittest.TestCase):
    def test_does_not_detect_truncation_with_literal_inner_fence(self):
        # 使用缩进处理含字面 ``` 围栏的 data 块，不应误判为截断
        text = (
            "```chat2cli\n"
            f"{IND}<data.code>\n"
            f"{IND}```\n"
            f"{IND}literal fence content\n"
            f"{IND}```\n"
            f"{IND}</data.code>\n"
            f'{IND}<request>\n{IND}{{"method":"skill"}}\n{IND}</request>\n'
            "```"
        )
        self.assertFalse(chat2cli.has_truncated_fence(text)[0])

    def test_no_fence_at_all(self):
        text = "no fence here"
        self.assertFalse(chat2cli.has_truncated_fence(text)[0])

    def test_valid_three_backtick_fence(self):
        # 正常的三反引号围栏，无截断
        text = (
            "```chat2cli\n"
            '<request>\n{"method":"skill"}\n</request>\n'
            "```"
        )
        self.assertFalse(chat2cli.has_truncated_fence(text)[0])

    def test_response_output_is_not_truncation(self):
        # chat2cli 自身输出回灌（data + response，无 request）不是截断
        text = (
            "```chat2cli\n"
            "<data.view_1>hello</data.view_1>\n"
            "<response>\n"
            '{"jsonrpc":"2.0","id":1,"result":{"success":true}}\n'
            "</response>\n"
            "```"
        )
        self.assertFalse(chat2cli.has_truncated_fence(text)[0])

    def test_complete_data_block_without_request_is_not_truncation(self):
        text = "```chat2cli\n<data.x>hello</data.x>\n```"
        self.assertFalse(chat2cli.has_truncated_fence(text)[0])

    def test_unclosed_data_tag_is_truncation(self):
        # data 块内含字面围栏导致外层围栏提前闭合，只剩未闭合的 <data.code>
        text = (
            "```chat2cli\n"
            "<data.code>\n"
            "```\n"
            "literal fence content\n"
            "```\n"
            "</data.code>\n"
            '<request>{"jsonrpc":"2.0","id":1,"method":"pwsh",'
            '"params":{"command":"echo hi"}}</request>\n'
            "```"
        )
        self.assertTrue(chat2cli.has_truncated_fence(text)[0])


class TestFenceForContent(unittest.TestCase):
    def test_no_backticks_uses_minimum_three(self):
        self.assertEqual(chat2cli._fence_for_content("plain text"), "```")

    def test_empty_content_uses_minimum_three(self):
        self.assertEqual(chat2cli._fence_for_content(""), "```")

    def test_three_backticks_requires_four(self):
        self.assertEqual(chat2cli._fence_for_content("```code```"), "````")

    def test_four_backticks_requires_five(self):
        self.assertEqual(chat2cli._fence_for_content("````code````"), "`````")

    def test_longest_run_across_multiline_content(self):
        # 多个围栏中取最长，散落在多行内容中
        content = "line1\n```\nline2\n`````\nline3"
        self.assertEqual(chat2cli._fence_for_content(content), "``````")

    def test_resulting_fence_is_always_longer_than_longest_run(self):
        # 对多种输入验证围栏反引号数 > 内容最长反引号序列
        for content in ["", "x", "`", "```", "a```b````c", "\n`````\n"]:
            fence = chat2cli._fence_for_content(content)
            longest_run = max(
                (len(m) for m in __import__("re").findall(r"`+", content)),
                default=0,
            )
            self.assertGreater(len(fence), longest_run, content)
            self.assertGreaterEqual(len(fence), 3, content)


class TestViewOobId(unittest.TestCase):
    def test_view_file_ref_id_uses_rpc_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            target = tmp / "example.txt"
            target.write_text("line1\nline2\n", encoding="utf-8")

            meta, content_block = chat2cli.view_file("42", str(target), {})

        self.assertTrue(meta["success"])
        self.assertEqual(meta["content"]["ref"], "view_42")
        self.assertTrue(content_block.startswith("<data.view_42>"))

    def test_view_directory_ref_id_uses_rpc_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            (tmp / "file.txt").write_text("x", encoding="utf-8")

            meta, content_block = chat2cli.view_directory("7", tmpdir)

        self.assertTrue(meta["success"])
        self.assertEqual(meta["content"]["ref"], "view_7")
        self.assertTrue(content_block.startswith("<data.view_7>"))


class TestEmitResultTextOverlong(unittest.TestCase):
    """覆盖 _emit_result_text 超长输出落盘与 head/tail 引用行为"""

    def setUp(self):
        # 清空模块全局 pending，避免测试间串扰
        chat2cli._pending_oob_data.clear()

    def _make_overlong_text(self, lines: int = 100) -> str:
        """构造超过 _FILE_THRESHOLD 的多行文本，每行内容可识别行号"""
        line = "x" * 200
        parts = [f"{i:04d}:{line}" for i in range(1, lines + 1)]
        text = "\n".join(parts)
        self.assertGreaterEqual(len(text), chat2cli._FILE_THRESHOLD)
        return text

    def test_overlong_returns_dict_with_path_and_refs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                result = chat2cli._emit_result_text(
                    "42", "stdout", self._make_overlong_text()
                )
            finally:
                os.chdir(old_cwd)

        self.assertIsInstance(result, dict)
        self.assertIn("message", result)
        self.assertIn("path", result)
        self.assertEqual(result["head"], {"ref": "stdout_42_head"})
        self.assertEqual(result["tail"], {"ref": "stdout_42_tail"})

    def test_overlong_head_starts_at_line_one(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                chat2cli._emit_result_text("1", "stderr", self._make_overlong_text())
            finally:
                os.chdir(old_cwd)

        head = chat2cli._pending_oob_data["stderr_1_head"]
        self.assertTrue(head.startswith("1:0001:"))

    def test_overlong_tail_preserves_real_line_numbers(self):
        text = self._make_overlong_text(lines=100)
        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                chat2cli._emit_result_text("7", "stdout", text)
            finally:
                os.chdir(old_cwd)

        tail = chat2cli._pending_oob_data["stdout_7_tail"]
        # 最后一行是第 100 行，行号必须正确保留
        self.assertTrue(tail.endswith("100:0100:" + "x" * 200))
        # tail 首行必须是完整行，以行号开头，不出现半行内容
        first_line = tail.splitlines()[0]
        self.assertRegex(first_line, r"^\d+:\d{4}:x{200}$")

    def test_overlong_scratch_file_uses_stream_id_naming(self):
        text = self._make_overlong_text()
        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                result = chat2cli._emit_result_text("abc-1", "stdout", text)
                path = Path(os.path.expanduser(result["path"]))
                self.assertTrue(path.exists())
                self.assertEqual(path.name, "stdout_abc-1.txt")
                self.assertEqual(path.read_text(encoding="utf-8"), text)
            finally:
                os.chdir(old_cwd)


class TestOutputFenceLength(unittest.TestCase):
    """stdout 输出的 chat2cli 代码块围栏必须比内容中最长反引号序列更长"""

    def _run_chat2cli(self, input_text: str) -> str:
        import subprocess
        import sys

        script = Path(__file__).with_name("chat2cli.py")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [sys.executable, str(script)],
                input=input_text,
                capture_output=True,
                text=True,
                encoding="utf-8",
                cwd=tmpdir,
                check=False,
            )
        return result.stdout

    def _longest_backtick_run(self, text: str) -> int:
        import re
        return max((len(m) for m in re.findall(r"`+", text)), default=0)

    def test_output_fence_longer_than_content_backticks(self):
        # pwsh 输出包含 ``` 内容时，外层围栏必须更长为 ````
        command = "Write-Output '```inner```'"
        input_text = (
            "```chat2cli\n"
            "<request>\n"
            f'{{"jsonrpc":"2.0","id":1,"method":"pwsh","params":{{"command":"{command}"}}}}\n'
            "</request>\n"
            "```"
        )
        output = self._run_chat2cli(input_text)

        # 提取 stdout 输出 chat2cli 代码块的开头围栏
        fence_match = __import__("re").match(r"(`+)chat2cli", output)
        self.assertIsNotNone(fence_match, "输出应以 chat2cli 围栏开头")
        fence = fence_match.group(1)

        # 只检查围栏内部内容的最长反引号序列（排除外层围栏本身）
        block_start = len(fence) + len("chat2cli")
        block_end = output.rstrip().rfind(fence)
        inner = output[block_start:block_end]
        inner_longest = self._longest_backtick_run(inner)
        self.assertGreater(len(fence), inner_longest)
        # 内容包含 ```，围栏必须至少为 ````
        self.assertGreaterEqual(len(fence), 4)

    def test_output_fence_longer_when_oob_data_contains_long_fence(self):
        # 构造超长 stdout，内容中含有 ````，触发 OOB 数据块
        long_text = "````" + ("x" * (chat2cli._FILE_THRESHOLD + 100))
        command = f"Write-Output '{long_text}'"
        input_text = (
            "```chat2cli\n"
            "<request>\n"
            f'{{"jsonrpc":"2.0","id":1,"method":"pwsh","params":{{"command":"{command}"}}}}\n'
            "</request>\n"
            "```"
        )
        output = self._run_chat2cli(input_text)

        fence_match = __import__("re").match(r"(`+)chat2cli", output)
        self.assertIsNotNone(fence_match, "输出应以 chat2cli 围栏开头")
        fence = fence_match.group(1)

        # 只检查围栏内部内容的最长反引号序列（排除外层围栏本身）
        block_start = len(fence) + len("chat2cli")
        block_end = output.rstrip().rfind(fence)
        inner = output[block_start:block_end]
        inner_longest = self._longest_backtick_run(inner)
        self.assertGreater(len(fence), inner_longest)
        # 内容含 ````，围栏至少为 `````
        self.assertGreaterEqual(len(fence), 5)

    def test_normal_output_uses_three_backtick_fence(self):
        # 内容不含反引号时，围栏保持三个反引号
        input_text = (
            "```chat2cli\n"
            "<request>\n"
            '{"jsonrpc":"2.0","id":1,"method":"pwsh","params":{"command":"Write-Output hello"}}\n'
            "</request>\n"
            "```"
        )
        output = self._run_chat2cli(input_text)
        self.assertTrue(output.startswith("```chat2cli\n"))


class TestErrorInstructionWrapping(unittest.TestCase):
    """错误提示应包裹在 <chat2cli_instruction> 标签内，而不是直接作为正文返回"""

    def _run_chat2cli(self, input_text: str) -> str:
        import subprocess
        import sys

        script = Path(__file__).with_name("chat2cli.py")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [sys.executable, str(script)],
                input=input_text,
                capture_output=True,
                text=True,
                encoding="utf-8",
                cwd=tmpdir,
                check=False,
            )
        return result.stdout

    def test_invalid_indent_error_wrapped_in_instruction_tag(self):
        text = (
            "```chat2cli\n"
            ":<request>\n"
            '{"method":"pwsh"}\n'
            ":</request>\n"
            "```"
        )
        output = self._run_chat2cli(text)
        self.assertTrue(output.startswith("<chat2cli_instruction>\n"))
        self.assertTrue(output.rstrip().endswith("</chat2cli_instruction>"))

    def test_bare_request_error_wrapped_in_instruction_tag(self):
        text = (
            "<request>\n"
            '{"method":"pwsh"}\n'
            "</request>\n"
        )
        output = self._run_chat2cli(text)
        self.assertTrue(output.startswith("<chat2cli_instruction>\n"))
        self.assertTrue(output.rstrip().endswith("</chat2cli_instruction>"))


class TestResponseOutputHandling(unittest.TestCase):
    """chat2cli 自身输出回灌（data + response，无 request）应输出初始指令而非报错。"""

    RESPONSE_OUTPUT = (
        "```chat2cli\n"
        "<data.view_1>hello</data.view_1>\n"
        "<response>\n"
        '{"jsonrpc":"2.0","id":1,"result":{"success":true}}\n'
        "</response>\n"
        "```"
    )

    def _run_chat2cli(self, input_text: str) -> str:
        import subprocess
        import sys

        script = Path(__file__).with_name("chat2cli.py")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [sys.executable, str(script)],
                input=input_text,
                capture_output=True,
                text=True,
                encoding="utf-8",
                cwd=tmpdir,
                check=False,
            )
        return result.stdout

    def test_prints_initial_instruction_instead_of_error(self):
        output = self._run_chat2cli(self.RESPONSE_OUTPUT)
        self.assertTrue(output.startswith("<chat2cli_instruction>\n"))
        self.assertIn(
            "chat2cli 是一种在用户本地把对话转换为可执行命令的语言", output
        )
        self.assertNotIn("无法完整识别", output)


def _tempdir_outside_git_repo():
    """返回一个位于 git 仓库之外的临时根目录；找不到时返回 None。

    沙箱内 TEMP/TMP 被重定向到仓库内的 .scratch/cache，此时不存在可用的
    仓库外位置，调用方应跳过相关测试而不是断言一个假场景。
    """
    import subprocess

    candidate = tempfile.gettempdir()
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=candidate,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    return None if result.returncode == 0 else candidate


class TestGitRootHint(unittest.TestCase):
    """初始指令触发时，若 cwd 位于 git 仓库内但不是仓库根目录，应在 stderr 提醒"""

    def _run_chat2cli(self, cwd: str):
        import subprocess
        import sys

        script = Path(__file__).with_name("chat2cli.py")
        return subprocess.run(
            [sys.executable, str(script)],
            input="",
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=cwd,
            check=False,
        )

    def test_warns_when_cwd_is_subdirectory_of_git_root(self):
        import subprocess

        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(["git", "init", "-q", tmpdir], check=True)
            subdir = os.path.join(tmpdir, "sub")
            os.makedirs(subdir)
            result = self._run_chat2cli(subdir)
        self.assertIn("不是 git 仓库根目录", result.stderr)

    def test_no_warning_when_cwd_is_git_root(self):
        import subprocess

        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(["git", "init", "-q", tmpdir], check=True)
            result = self._run_chat2cli(tmpdir)
        self.assertNotIn("不是 git 仓库根目录", result.stderr)

    def test_no_warning_outside_git_repo(self):
        base = _tempdir_outside_git_repo()
        if base is None:
            self.skipTest(
                "临时目录位于 git 仓库内（沙箱重定向），无法构造仓库外场景"
            )
        with tempfile.TemporaryDirectory(dir=base) as tmpdir:
            result = self._run_chat2cli(tmpdir)
        self.assertNotIn("不是 git 仓库根目录", result.stderr)


class TestEmitResultTextOobSelection(unittest.TestCase):
    """覆盖 OOB vs JSON 内联选择的阈值判断"""

    def setUp(self):
        chat2cli._pending_oob_data.clear()

    def _overhead(self, text: str, ref_id: str) -> tuple[int, int]:
        """计算 JSON 编码膨胀量与 OOB 固定开销"""
        import json
        json_len = len(json.dumps(text, ensure_ascii=False))
        return json_len - len(text), 26 + 3 * len(ref_id)

    def test_uses_oob_when_escaping_overhead_exceeds_fixed_cost(self):
        # 大量换行导致 JSON 膨胀，超过 OOB 固定开销
        text = "\n".join(str(i) for i in range(200))
        overhead, fixed = self._overhead(text, "stdout_1")
        self.assertGreater(overhead, fixed)

        result = chat2cli._emit_result_text(1, "stdout", text)
        self.assertEqual(result, {"ref": "stdout_1"})
        self.assertIn("stdout_1", chat2cli._pending_oob_data)

    def test_uses_inline_when_escaping_overhead_below_fixed_cost(self):
        # 纯文本无转义，JSON 膨胀小，内联更短
        text = "plain text without special characters"
        overhead, fixed = self._overhead(text, "stdout_1")
        self.assertLess(overhead, fixed)

        result = chat2cli._emit_result_text(1, "stdout", text)
        self.assertEqual(result, text)
        self.assertNotIn("stdout_1", chat2cli._pending_oob_data)



class TestPreprocessCommonMistakes(unittest.TestCase):
    """常见错误格式预处理：冒号缩进缺围栏、XML 风格 tool call"""

    def test_valid_chat2cli_block_is_unchanged(self):
        text = (
            "```chat2cli\n"
            '<request>\n{"method":"skill"}\n</request>\n'
            "```"
        )
        processed, reminders = chat2cli.preprocess_common_mistakes(text)
        self.assertEqual(processed, text)
        self.assertEqual(reminders, [])

    def test_indented_without_fence_is_wrapped(self):
        text = (
            ':<request>\n'
            ':{"jsonrpc":"2.0","id":1,"method":"skill","params":{"name":"x"}}\n'
            ':</request>\n'
        )
        processed, reminders = chat2cli.preprocess_common_mistakes(text)
        self.assertTrue(processed.startswith("```chat2cli\n"))
        self.assertTrue(processed.rstrip().endswith("```"))
        self.assertTrue(reminders)
        blocks = chat2cli.extract_chat2cli_blocks(processed)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["method"], "skill")

    def test_anthropic_tool_call_is_converted(self):
        text = (
            '<invoke name="str_replace_editor">\n'
            '<parameter name="command">view</parameter>\n'
            '<parameter name="path">C:\\x\\file.py</parameter>\n'
            "</invoke>\n"
        )
        processed, reminders = chat2cli.preprocess_common_mistakes(text)
        self.assertTrue(reminders)
        blocks = chat2cli.extract_chat2cli_blocks(processed)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["method"], "str_replace_editor")
        self.assertEqual(blocks[0]["params"]["command"], "view")
        self.assertEqual(blocks[0]["params"]["path"], "C:\\x\\file.py")

    def test_openai_tool_calls_are_converted(self):
        text = (
            "<|tool_calls>\n"
            '<|invoke name="str_replace_editor">\n'
            '<|parameter name="command" string="true">view</|parameter>\n'
            '<|parameter name="path" string="true">C:\\x\\file.py</|parameter>\n'
            "</|invoke>\n"
            '<|invoke name="pwsh">\n'
            '<|parameter name="command" string="true">echo hi</|parameter>\n'
            "</|invoke>\n"
            "</|tool_calls>\n"
        )
        processed, reminders = chat2cli.preprocess_common_mistakes(text)
        self.assertTrue(reminders)
        blocks = chat2cli.extract_chat2cli_blocks(processed)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]["method"], "str_replace_editor")
        self.assertEqual(blocks[0]["params"]["command"], "view")
        self.assertEqual(blocks[1]["method"], "pwsh")
        self.assertEqual(blocks[1]["params"]["command"], "echo hi")

    def test_tool_call_string_true_keeps_string_type(self):
        text = (
            "<|tool_calls>\n"
            '<|invoke name="str_replace_editor">\n'
            '<|parameter name="insert_line" string="true">5</|parameter>\n'
            "</|invoke>\n"
            "</|tool_calls>\n"
        )
        processed, _ = chat2cli.preprocess_common_mistakes(text)
        blocks = chat2cli.extract_chat2cli_blocks(processed)
        self.assertEqual(blocks[0]["params"]["insert_line"], "5")

    def test_tool_call_without_string_parses_json_value(self):
        text = (
            '<invoke name="str_replace_editor">\n'
            '<parameter name="insert_line">5</parameter>\n'
            "</invoke>\n"
        )
        processed, _ = chat2cli.preprocess_common_mistakes(text)
        blocks = chat2cli.extract_chat2cli_blocks(processed)
        self.assertEqual(blocks[0]["params"]["insert_line"], 5)



    def test_fenced_block_with_toolcall_literal_is_unchanged(self):
        # 已含合法 chat2cli 围栏时，data 块内的字面 tool call 不应被转换
        text = (
            "```chat2cli\n"
            ":<data.example>\n"
            ':<|tool_calls><|invoke name="pwsh"><|parameter name="command" string="true">echo hi</|parameter></|invoke></|tool_calls>\n'
            ":</data.example>\n"
            ':<request>\n:{"method":"skill"}\n:</request>\n'
            "```"
        )
        processed, reminders = chat2cli.preprocess_common_mistakes(text)
        self.assertEqual(processed, text)
        self.assertEqual(reminders, [])

    def test_fenced_block_anywhere_skips_preprocessing(self):
        # 只要出现 chat2cli 围栏，就不再尝试任何预处理
        text = (
            "前言\n"
            '<invoke name="pwsh"><parameter name="command">echo hi</parameter></invoke>\n'
            "```chat2cli\n"
            ':<request>\n:{"method":"skill"}\n:</request>\n'
            "```"
        )
        processed, reminders = chat2cli.preprocess_common_mistakes(text)
        self.assertEqual(processed, text)
        self.assertEqual(reminders, [])

    def test_unknown_format_returns_unchanged(self):
        text = "just a normal conversation without any special format"
        processed, reminders = chat2cli.preprocess_common_mistakes(text)
        self.assertEqual(processed, text)
        self.assertEqual(reminders, [])




    def test_dsml_chat2cli_multiple_requests_array(self):
        # 用户实际场景：request 参数是含多个 pwsh 请求的 JSON 数组
        payload = (
            "[\n"
            "  {\n"
            '    "jsonrpc": "2.0",\n'
            '    "id": 1,\n'
            '    "method": "pwsh",\n'
            '    "params": {"command": "echo one"}\n'
            "  },\n"
            "  {\n"
            '    "jsonrpc": "2.0",\n'
            '    "id": 2,\n'
            '    "method": "pwsh",\n'
            '    "params": {"command": "echo two"}\n'
            "  }\n"
            "]"
        )
        text = (
            "<｜｜DSML｜｜ calls>\n"
            '<｜｜DSML｜｜ invoke name="chat2cli">\n'
            '<｜｜DSML｜｜ parameter name="request" string="true">'
            + payload
            + "</｜｜DSML｜｜ parameter>\n"
            "</｜｜DSML｜｜ invoke>\n"
            "</｜｜DSML｜｜ calls>\n"
        )
        processed, reminders = chat2cli.preprocess_common_mistakes(text)
        self.assertTrue(reminders)
        blocks = chat2cli.extract_chat2cli_blocks(processed)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]["params"]["command"], "echo one")
        self.assertEqual(blocks[1]["params"]["command"], "echo two")

    def test_dsml_marker_without_invoke_still_reminds(self):
        # 检测到 DSML 特征但无法转换时，也应提示模型改用标准格式
        text = (
            "<｜｜DSML｜｜ calls>\n"
            '<｜｜DSML｜｜ parameter name="request">garbage</｜｜DSML｜｜ parameter>\n'
            "</｜｜DSML｜｜ calls>\n"
        )
        processed, reminders = chat2cli.preprocess_common_mistakes(text)
        self.assertEqual(processed, text)
        self.assertTrue(reminders)

    def test_pipe_dsml_variant_is_converted(self):
        text = (
            '<|DSML|invoke name="pwsh">\n'
            '<|DSML|parameter name="command">echo hi</|DSML|parameter>\n'
            "</|DSML|invoke>\n"
        )
        processed, reminders = chat2cli.preprocess_common_mistakes(text)
        self.assertTrue(reminders)
        blocks = chat2cli.extract_chat2cli_blocks(processed)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["method"], "pwsh")
        self.assertEqual(blocks[0]["params"]["command"], "echo hi")

    def test_bom_before_indented_input_is_stripped(self):

        text = (
            "\ufeff"
            ':<request>\n'
            ':{"method":"skill"}\n'
            ':</request>\n'
        )
        processed, reminders = chat2cli.preprocess_common_mistakes(text)
        self.assertTrue(processed.startswith("```chat2cli\n"))
        self.assertTrue(reminders)
        blocks = chat2cli.extract_chat2cli_blocks(processed)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["method"], "skill")



    def test_dsml_chat2cli_invoke_is_expanded(self):
        # DSML 是模型幻觉格式：chat2cli 工具的 request 参数里是完整 JSON-RPC
        text = (
            "<｜｜DSML｜｜ calls>\n"
            '<｜｜DSML｜｜ invoke name="chat2cli">\n'
            '<｜｜DSML｜｜ parameter name="request" string="true">'
            '[\n  {\n    "jsonrpc": "2.0",\n    "id": 1,\n'
            '    "method": "pwsh",\n'
            '    "params": {"command": "echo hi"}\n  }\n]'
            "</｜｜DSML｜｜ parameter>\n"
            "</｜｜DSML｜｜ invoke>\n"
            "</｜｜DSML｜｜ calls>\n"
        )
        processed, reminders = chat2cli.preprocess_common_mistakes(text)
        self.assertTrue(reminders)
        blocks = chat2cli.extract_chat2cli_blocks(processed)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["method"], "pwsh")
        self.assertEqual(blocks[0]["params"]["command"], "echo hi")






class TestInputNeedsProcessing(unittest.TestCase):
    """--check 模式分类：判断输入是否需要 chat2cli 处理（而非输出初始指令）"""

    def test_empty_input_returns_false(self):
        self.assertFalse(chat2cli.input_needs_processing(""))
        self.assertFalse(chat2cli.input_needs_processing("   \n  "))

    def test_unrecognized_text_returns_false(self):
        self.assertFalse(
            chat2cli.input_needs_processing("just a normal conversation")
        )

    def test_valid_request_returns_true(self):
        text = (
            "```chat2cli\n"
            '<request>\n{"method":"pwsh","params":{"command":"echo hi"}}\n</request>\n'
            "```"
        )
        self.assertTrue(chat2cli.input_needs_processing(text))

    def test_indented_without_fence_returns_true(self):
        text = (
            ':<request>\n'
            ':{"method":"pwsh","params":{"command":"echo hi"}}\n'
            ':</request>\n'
        )
        self.assertTrue(chat2cli.input_needs_processing(text))

    def test_toolcall_returns_true(self):
        text = (
            '<invoke name="pwsh">\n'
            '<parameter name="command">echo hi</parameter>\n'
            "</invoke>\n"
        )
        self.assertTrue(chat2cli.input_needs_processing(text))

    def test_truncated_fence_returns_true(self):
        # 围栏未闭合属于格式错误，需要提示
        text = '```chat2cli\n:<request>\n:{"method":"pwsh"}\n'
        self.assertTrue(chat2cli.input_needs_processing(text))

    def test_bare_request_returns_true(self):
        text = '<request>\n{"method":"pwsh"}\n</request>\n'
        self.assertTrue(chat2cli.input_needs_processing(text))

    def test_invalid_indent_returns_true(self):
        # 缩进非法属于格式错误，需要提示
        text = (
            "```chat2cli\n"
            ":<request>\n"
            '{"method":"pwsh"}\n'
            ":</request>\n"
            "```"
        )
        self.assertTrue(chat2cli.input_needs_processing(text))

    def test_response_output_returns_false(self):
        # chat2cli 自身输出回灌不需要执行任何 RPC
        text = (
            "```chat2cli\n"
            "<data.view_1>hello</data.view_1>\n"
            "<response>\n"
            '{"jsonrpc":"2.0","id":1,"result":{"success":true}}\n'
            "</response>\n"
            "```"
        )
        self.assertFalse(chat2cli.input_needs_processing(text))



class TestCreateCommandAutoParentDir(unittest.TestCase):
    """create 命令应自动创建缺失的父级目录"""

    def _create_in_tmpdir(self, rel_path: str, file_text: str):
        """在临时目录内执行 create，返回 (meta, 目标文件内容或 None)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                target = os.path.join(tmpdir, *rel_path.split("/"))
                meta, _ = chat2cli.execute_str_replace_editor(
                    "1",
                    {
                        "command": "create",
                        "path": target,
                        "file_text": file_text,
                    },
                )
                content = None
                if os.path.isfile(target):
                    content = Path(target).read_text(encoding="utf-8")
            finally:
                os.chdir(old_cwd)
        return meta, content

    def test_creates_missing_parent_directories(self):
        meta, content = self._create_in_tmpdir("a/b/c/file.txt", "hello")
        self.assertTrue(meta["success"])
        self.assertEqual(content, "hello")

    def test_fails_when_file_already_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                target = os.path.join(tmpdir, "exists.txt")
                Path(target).write_text("old", encoding="utf-8")
                meta, _ = chat2cli.execute_str_replace_editor(
                    "1",
                    {
                        "command": "create",
                        "path": target,
                        "file_text": "new",
                    },
                )
                content = Path(target).read_text(encoding="utf-8")
            finally:
                os.chdir(old_cwd)
        self.assertFalse(meta["success"])
        self.assertEqual(content, "old")




class TestBuildPwshEnv(unittest.TestCase):
    """execute_pwsh 为子进程构建的环境变量"""

    def test_injects_utf8_env_vars_for_common_tools(self):
        # Python / WSL / POSIX 工具的 UTF-8 环境变量
        env = chat2cli._build_pwsh_env({})
        self.assertEqual(env["PYTHONUTF8"], "1")
        self.assertEqual(env["PYTHONIOENCODING"], "utf-8")
        self.assertEqual(env["WSL_UTF8"], "1")
        self.assertEqual(env["LANG"], "C.UTF-8")
        self.assertEqual(env["LC_ALL"], "C.UTF-8")

    def test_injects_ci_and_no_color(self):
        env = chat2cli._build_pwsh_env({})
        self.assertEqual(env["CI"], "true")
        self.assertEqual(env["NO_COLOR"], "1")

    def test_injects_data_blocks_as_env(self):
        env = chat2cli._build_pwsh_env({"foo": "bar"})
        self.assertEqual(env["DATA_foo"], "bar")

    def test_returns_copy_without_mutating_os_environ(self):
        saved = os.environ.pop("WSL_UTF8", None)
        try:
            chat2cli._build_pwsh_env({})
            self.assertNotIn("WSL_UTF8", os.environ)
        finally:
            if saved is not None:
                os.environ["WSL_UTF8"] = saved



class TestCollectSecretValues(unittest.TestCase):
    """从环境映射收集敏感值用于值驱动脱敏。

    全部通过注入的普通 dict 完成，既不读取也不改写真实 os.environ，
    避免真实密钥出现在断言输出中。
    """

    def test_collects_secret_prefixed_values(self):
        self.assertEqual(
            chat2cli._collect_secret_values({"SECRET_FOO": "supersecretvalue"}),
            {"SECRET_FOO": "supersecretvalue"},
        )

    def test_ignores_other_variables(self):
        self.assertEqual(
            chat2cli._collect_secret_values({"HARMLESS_VARIABLE": "supersecretvalue"}),
            {},
        )

    def test_ignores_auto_detected_values_shorter_than_threshold(self):
        # 自动识别（非显式 SECRET_ 前缀）的短值仍受阈值保护
        self.assertEqual(chat2cli._collect_secret_values({"SOME_TOKEN": "abc"}), {})

    def test_secret_prefix_has_no_length_threshold(self):
        # SECRET_ 前缀是用户显式声明，短值也必须脱敏
        self.assertEqual(
            chat2cli._collect_secret_values({"SECRET_DOMAIN": "abc.com"}),
            {"SECRET_DOMAIN": "abc.com"},
        )

    def test_secret_prefix_empty_value_is_ignored(self):
        # 空值会在任意位置匹配，必须排除
        self.assertEqual(chat2cli._collect_secret_values({"SECRET_EMPTY": ""}), {})

    def test_collects_token_suffix_and_structural_names(self):
        env = {
            "SOME_TOKEN": "tokenvalue123",
            "USERNAME": "abcde",
            "COMPUTERNAME": "DESKTOP-XYZ",
        }
        self.assertEqual(
            chat2cli._collect_secret_values(env),
            {
                "SOME_TOKEN": "tokenvalue123",
                "USERNAME": "abcde",
                "COMPUTERNAME": "DESKTOP-XYZ",
            },
        )

    def test_structural_name_below_threshold_is_ignored(self):
        # 结构性变量阈值 4，低于阈值的值不参与替换
        self.assertEqual(chat2cli._collect_secret_values({"USERNAME": "abc"}), {})


class TestRedactText(unittest.TestCase):
    """值驱动 + 模式驱动的文本脱敏"""

    def test_replaces_known_value_with_env_reference(self):
        redacted, hits = chat2cli._redact_text(
            "token supersecretvalue end", {"SECRET_FOO": "supersecretvalue"}
        )
        self.assertEqual(redacted, 'token <redacted env="SECRET_FOO"> end')
        self.assertEqual(hits, {"SECRET_FOO": 1})

    def test_longer_value_replaced_before_shorter_substring(self):
        # 短值恰好是长值子串时，必须先替换长值，否则长值被切断
        redacted, _ = chat2cli._redact_text(
            "abcdefghijklmnop",
            {"SECRET_A": "abcdefghijklmnop", "SECRET_B": "abcdefghijkl"},
        )
        self.assertEqual(redacted, '<redacted env="SECRET_A">')

    def test_counts_all_occurrences(self):
        _, hits = chat2cli._redact_text(
            "supersecret supersecret", {"SECRET_FOO": "supersecret"}
        )
        self.assertEqual(hits, {"SECRET_FOO": 2})

    def test_no_match_returns_original(self):
        redacted, hits = chat2cli._redact_text("plain", {"SECRET_FOO": "zzzzzz"})
        self.assertEqual(redacted, "plain")
        self.assertEqual(hits, {})

    def test_redacts_sk_token_with_regex_label(self):
        redacted, hits = chat2cli._redact_text(
            "key sk-abcdefghijklmnopqrstuvwx end", {}
        )
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwx", redacted)
        self.assertIn("sk-[A-Za-z0-9_-]{20,}", redacted)
        self.assertEqual(hits, {"sk-[A-Za-z0-9_-]{20,}": 1})

    def test_redacts_github_token(self):
        token = "ghp_" + "a" * 36
        redacted, hits = chat2cli._redact_text(f"x {token} y", {})
        self.assertNotIn(token, redacted)
        self.assertEqual(hits, {"gh[pousr]_[A-Za-z0-9]{36,}": 1})

    def test_redacts_aws_access_key(self):
        redacted, hits = chat2cli._redact_text("AKIAABCDEFGHIJKLMNOP", {})
        self.assertNotIn("AKIAABCDEFGHIJKLMNOP", redacted)
        self.assertEqual(hits, {"AKIA[0-9A-Z]{16}": 1})

    def test_redacts_private_key_block(self):
        text = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "SECRETBODY\n"
            "-----END RSA PRIVATE KEY-----"
        )
        redacted, hits = chat2cli._redact_text(text, {})
        self.assertNotIn("SECRETBODY", redacted)
        self.assertEqual(len(hits), 1)

    def test_redacts_password_value_keeping_key_name(self):
        redacted, hits = chat2cli._redact_text('password: "hunter2secret"', {})
        self.assertIn("password", redacted)
        self.assertNotIn("hunter2secret", redacted)
        self.assertEqual(hits, {"key-value-secret": 1})

    def test_value_driven_runs_before_pattern_driven(self):
        redacted, hits = chat2cli._redact_text(
            "supersecretvalue", {"SECRET_FOO": "supersecretvalue"}
        )
        self.assertEqual(redacted, '<redacted env="SECRET_FOO">')
        self.assertEqual(hits, {"SECRET_FOO": 1})


    def test_value_driven_is_case_insensitive(self):
        # 输出里的值大小写与环境变量不一致时也必须脱敏
        redacted, hits = chat2cli._redact_text(
            "token SUPERSECRETVALUE end", {"SECRET_FOO": "supersecretvalue"}
        )
        self.assertEqual(redacted, 'token <redacted env="SECRET_FOO"> end')
        self.assertEqual(hits, {"SECRET_FOO": 1})

    def test_structural_value_is_case_insensitive(self):
        # 结构性短值同样按大小写不敏感匹配
        redacted, _ = chat2cli._redact_text(
            "ABCDE abcde", {"USERNAME": "abcde"}
        )
        self.assertEqual(
            redacted,
            '<redacted env="USERNAME"> <redacted env="USERNAME">',
        )

    def test_pattern_driven_is_case_insensitive(self):
        # 高置信度模式的大小写变体同样是凭证
        token = "SK-" + "A" * 24
        redacted, hits = chat2cli._redact_text(f"x {token} y", {})
        self.assertNotIn(token, redacted)
        self.assertEqual(hits, {"sk-[A-Za-z0-9_-]{20,}": 1})



class TestRedactNode(unittest.TestCase):
    """递归脱敏结构中的所有字符串字段"""

    def test_redacts_nested_string_fields(self):
        node = {"result": {"stdout": "sk-abcdefghijklmnopqrstuvwx", "path": "C:/x"}}
        redacted, hits = chat2cli._redact_node(node, {})
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwx", redacted["result"]["stdout"])
        self.assertEqual(redacted["result"]["path"], "C:/x")
        self.assertEqual(hits, {"result.stdout": {"sk-[A-Za-z0-9_-]{20,}": 1}})

    def test_redacts_error_message(self):
        node = {"error": {"message": "failed sk-abcdefghijklmnopqrstuvwx"}}
        redacted, _ = chat2cli._redact_node(node, {})
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwx", redacted["error"]["message"])

    def test_preserves_non_string_values(self):
        node = {"exit_code": 1, "success": True, "none": None}
        redacted, hits = chat2cli._redact_node(node, {})
        self.assertEqual(redacted, {"exit_code": 1, "success": True, "none": None})
        self.assertEqual(hits, {})

    def test_redacts_strings_inside_lists(self):
        node = {"items": ["sk-abcdefghijklmnopqrstuvwx"]}
        redacted, _ = chat2cli._redact_node(node, {})
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwx", redacted["items"][0])

    def test_does_not_mutate_input(self):
        node = {"stdout": "sk-abcdefghijklmnopqrstuvwx"}
        chat2cli._redact_node(node, {})
        self.assertEqual(node["stdout"], "sk-abcdefghijklmnopqrstuvwx")


class TestFormatRedactionReminder(unittest.TestCase):
    def test_lists_category_count_and_where(self):
        hits = {"request#1.result.stdout": {"sk-token": 2}}
        reminder = chat2cli._format_redaction_reminder(hits)
        self.assertIn("<system-reminder>", reminder)
        self.assertIn("sk-token", reminder)
        self.assertIn("request#1.result.stdout", reminder)
        self.assertIn("2", reminder)

    def test_empty_hits_returns_empty_string(self):
        self.assertEqual(chat2cli._format_redaction_reminder({}), "")


class TestRedactionEndToEnd(unittest.TestCase):
    """端到端：密钥在响应中被脱敏，并附带 system-reminder"""

    def _run_chat2cli(self, input_text: str, cwd: str, env_extra=None):
        import subprocess
        import sys

        script = Path(__file__).with_name("chat2cli.py")
        # 从干净基线构建子进程环境：剔除所有敏感命名变量，只注入测试
        # 显式提供的值，避免真实密钥进入子进程输出或断言。
        env = {
            key: value
            for key, value in os.environ.items()
            if not chat2cli._is_secret_variable_name(key)
        }
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            [sys.executable, str(script)],
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=cwd,
            env=env,
            check=False,
        )

    def _request(self, request_obj) -> str:
        import json

        return (
            "```chat2cli\n<request>\n"
            + json.dumps(request_obj)
            + "\n</request>\n```"
        )

    def test_secret_env_value_redacted_in_response(self):
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "pwsh",
            "params": {"command": "Write-Output $env:SECRET_TEST"},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._run_chat2cli(
                self._request(request), tmpdir, {"SECRET_TEST": "supersecretvalue"}
            )
        self.assertNotIn("supersecretvalue", result.stdout)
        # 响应里是 JSON，引号会被转义
        self.assertIn('<redacted env=\\"SECRET_TEST\\">', result.stdout)
        self.assertIn("<system-reminder>", result.stdout)

    def test_pattern_token_redacted_in_response(self):
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "pwsh",
            "params": {"command": "Write-Output sk-abcdefghijklmnopqrstuvwx"},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._run_chat2cli(self._request(request), tmpdir)
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwx", result.stdout)
        self.assertIn("<system-reminder>", result.stdout)

    def test_view_output_redacted_in_response(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "secret.txt"
            target.write_text("token=sk-abcdefghijklmnopqrstuvwx\n", encoding="utf-8")
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "str_replace_editor",
                "params": {"command": "view", "path": str(target)},
            }
            result = self._run_chat2cli(self._request(request), tmpdir)
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwx", result.stdout)

    def test_scratch_file_keeps_raw_content(self):
        token = "sk-" + "a" * 100
        command = f"1..500 | ForEach-Object {{ Write-Output '{token}' }}"
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "pwsh",
            "params": {"command": command},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._run_chat2cli(self._request(request), tmpdir)
            self.assertNotIn(token, result.stdout)
            scratch_files = list(Path(tmpdir).glob(".scratch/**/stdout_1.txt"))
            self.assertEqual(len(scratch_files), 1)
            self.assertIn(token, scratch_files[0].read_text(encoding="utf-8"))



class TestSecretVariableNames(unittest.TestCase):
    """敏感变量名识别：按名称形状，不假设固定环境"""

    def test_secret_prefix_is_recognized(self):
        self.assertTrue(chat2cli._is_secret_variable_name("SECRET_FOO"))

    def test_token_suffix_is_recognized(self):
        self.assertTrue(chat2cli._is_secret_variable_name("GOTIFY_TOKEN"))

    def test_api_key_suffix_is_recognized(self):
        self.assertTrue(chat2cli._is_secret_variable_name("OPENAI_API_KEY"))

    def test_password_variants_are_recognized(self):
        for name in ("DB_PASSWORD", "DB_PASSWD", "MYSQL_PWD", "APP_SECRET"):
            self.assertTrue(chat2cli._is_secret_variable_name(name), name)

    def test_structural_names_are_recognized(self):
        for name in ("USERNAME", "USER", "LOGNAME", "COMPUTERNAME", "HOSTNAME"):
            self.assertTrue(chat2cli._is_secret_variable_name(name), name)

    def test_unrelated_name_is_not_recognized(self):
        self.assertFalse(chat2cli._is_secret_variable_name("PATH"))
        self.assertFalse(chat2cli._is_secret_variable_name("TEMP"))


class TestStructuralValueRedaction(unittest.TestCase):
    """结构性短值（用户名、机器名）的阈值与词边界行为"""

    def test_structural_short_value_is_collected(self):
        self.assertEqual(
            chat2cli._collect_secret_values({"USERNAME": "abcde"}).get("USERNAME"),
            "abcde",
        )

    def test_structural_value_uses_word_boundary(self):
        # 短值仅在词边界处替换，避免切断粘连文本
        redacted, hits = chat2cli._redact_text(
            "abcde123abcde abcde", {"USERNAME": "abcde"}
        )
        self.assertEqual(redacted, 'abcde123abcde <redacted env="USERNAME">')
        self.assertEqual(hits, {"USERNAME": 1})





class TestColorizeRedactedSpans(unittest.TestCase):
    """stderr 实时流：单行内命中脱敏规则的片段着灰色"""

    def test_marks_matched_span_grey(self):
        colored = chat2cli._colorize_redacted_spans(
            "x supersecretvalue y", {"SECRET_FOO": "supersecretvalue"}, "\033[37m"
        )
        # 命中片段前缀灰色，且原文仍保留（终端只有用户可见）
        self.assertIn("\033[90msupersecretvalue", colored)
        self.assertIn("supersecretvalue", colored)

    def test_no_match_keeps_base_color_only(self):
        colored = chat2cli._colorize_redacted_spans("plain", {}, "\033[31m")
        self.assertEqual(colored, "\033[31mplain\033[0m")

    def test_pattern_match_is_marked(self):
        colored = chat2cli._colorize_redacted_spans(
            "key sk-abcdefghijklmnopqrstuvwx", {}, "\033[37m"
        )
        self.assertIn("\033[90msk-abcdefghijklmnopqrstuvwx", colored)


class TestFindRedactionSpans(unittest.TestCase):
    """span 检测：值驱动优先，区间不重叠"""

    def test_value_driven_span_wins_over_pattern(self):
        # 已知值优先还原为可重新执行的引用，不让模式规则抢先
        spans = chat2cli._find_redaction_spans(
            "supersecretvalue", {"SECRET_FOO": "supersecretvalue"}
        )
        self.assertEqual(spans, [(0, 16, "SECRET_FOO")])

    def test_spans_are_non_overlapping(self):
        spans = chat2cli._find_redaction_spans(
            "abcdefghijklmnop",
            {"SECRET_A": "abcdefghijklmnop", "SECRET_B": "abcdefghijkl"},
        )
        self.assertEqual(spans, [(0, 16, "SECRET_A")])



class TestDisplayPath(unittest.TestCase):
    """路径显示：home 目录内的路径显示为 ~/ 形式，便于在 JSON 中直接复用"""

    def test_path_inside_home_uses_tilde(self):
        home = os.path.expanduser("~")
        target = os.path.join(home, "Documents", "foo.txt")
        self.assertEqual(chat2cli._display_path(target), "~/Documents/foo.txt")

    def test_home_itself_is_tilde(self):
        self.assertEqual(chat2cli._display_path(os.path.expanduser("~")), "~")

    def test_path_outside_home_stays_absolute(self):
        # 驱动器根目录必不在 home 内
        outside = os.path.abspath(os.sep)
        self.assertEqual(chat2cli._display_path(outside), outside)

    def test_nested_path_uses_forward_slashes(self):
        home = os.path.expanduser("~")
        target = os.path.join(home, ".chat2cli", "AGENTS.md")
        self.assertEqual(chat2cli._display_path(target), "~/.chat2cli/AGENTS.md")


class TestSkillContentUsesTilde(unittest.TestCase):
    """skill 提示词与 meta 中的路径显示为 ~/ 形式

    home 内路径若原样输出，会带出本地用户名，随后被值驱动脱敏
    替换成 <redacted env="USERNAME">，导致路径不可用。
    """

    def test_skill_dir_under_home_shows_tilde(self):
        from unittest.mock import mock_open, patch

        home = os.path.expanduser("~")
        skill_dir = os.path.join(home, ".agents", "skills", "demo")
        saved = chat2cli._discovered_skills
        chat2cli._discovered_skills = {
            "demo": {
                "name": "demo",
                "description": "d",
                "path": skill_dir,
                "scope": "user",
            }
        }
        try:
            with patch("builtins.open", mock_open(read_data="body")):
                meta, content_block = chat2cli.execute_skill(1, {"name": "demo"})
        finally:
            chat2cli._discovered_skills = saved

        self.assertTrue(meta["success"])
        self.assertEqual(meta["path"], "~/.agents/skills/demo")
        self.assertIn(
            "Base directory for this skill: ~/.agents/skills/demo", content_block
        )
        self.assertNotIn(home, content_block)


class TestInstructionShowsTildeCwd(unittest.TestCase):
    """初始指令中，home 目录内的工作目录显示为 ~/ 形式"""

    def _render_instruction(self, cwd: str) -> str:
        import io
        from contextlib import redirect_stdout
        from unittest.mock import patch

        buf = io.StringIO()
        with patch("chat2cli.os.getcwd", return_value=cwd), patch(
            "chat2cli._git_root_mismatch_hint", return_value=None
        ), patch("chat2cli.discover_skills", return_value={}):
            with redirect_stdout(buf):
                chat2cli.print_instruction()
        return buf.getvalue()

    def test_home_cwd_shows_tilde(self):
        output = self._render_instruction(os.path.expanduser("~"))
        self.assertIn("当前工作目录：~", output)

    def test_outside_cwd_shows_absolute(self):
        outside = os.path.abspath(os.sep)
        output = self._render_instruction(outside)
        self.assertIn(f"当前工作目录：{outside}", output)


class TestArbitraryIndentChar(unittest.TestCase):
    """缩进字符由代码块首个非空行决定，任意非 '<' 字符均可用作缩进。"""

    def test_other_char_indent_is_supported(self):
        # 用 ';' 作为缩进字符，解析结果应与直接写死的前缀一致
        text = (
            "```chat2cli\n"
            ";<data.code>\n"
            ";line\n"
            ";</data.code>\n"
            ';<request>\n;{"method":"skill"}\n;</request>\n'
            "```"
        )
        blocks = chat2cli.extract_chat2cli_blocks(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["method"], "skill")
        data = chat2cli.extract_data_blocks(text)
        self.assertEqual(data["code"], "\nline\n")

    def test_mismatched_indent_char_raises_error(self):
        # 首个非空行用 ';' 缩进，后续行却用 ':' 缩进，应判为非法
        text = (
            "```chat2cli\n"
            ";<request>\n"
            '{"method":"pwsh"}\n'
            ";}</request>\n"
            "```"
        )
        with self.assertRaises(ValueError):
            chat2cli.extract_chat2cli_blocks(text)

    def test_indent_char_may_differ_from_configured(self):
        # 缩进字符按块检测，不必等于配置常量
        other = "#" if IND != "#" else "%"
        text = (
            "```chat2cli\n"
            f"{other}<request>\n"
            f'{other}{{"method":"skill"}}\n'
            f"{other}</request>\n"
            "```"
        )
        blocks = chat2cli.extract_chat2cli_blocks(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["method"], "skill")


class TestStderrRequestFeedback(unittest.TestCase):
    """每个请求（含执行失败与识别失败）都应在 stderr 有反馈，

    便于用户在终端直接区分“格式识别不出来”与“调用无效”。
    """

    def _run(self, input_text: str):
        import subprocess
        import sys

        script = Path(__file__).with_name("chat2cli.py")
        with tempfile.TemporaryDirectory() as tmpdir:
            return subprocess.run(
                [sys.executable, str(script)],
                input=input_text,
                capture_output=True,
                text=True,
                encoding="utf-8",
                cwd=tmpdir,
                check=False,
            )

    def _wrap(self, request_json: str) -> str:
        fence = "```"
        return "说明\n" + fence + "chat2cli\n<request>\n" + request_json + "\n</request>\n" + fence

    def test_unknown_method_reports_to_stderr(self):
        result = self._run(
            self._wrap('{"jsonrpc":"2.0","id":1,"method":"bogus","params":{}}')
        )
        self.assertIn("request#1", result.stderr)
        self.assertIn("bogus", result.stderr)

    def test_unknown_param_reports_to_stderr(self):
        result = self._run(
            self._wrap(
                '{"jsonrpc":"2.0","id":1,"method":"pwsh",'
                '"params":{"command":"echo hi","bogus":1}}'
            )
        )
        self.assertIn("request#1", result.stderr)
        self.assertIn("bogus", result.stderr)

    def test_missing_data_ref_reports_to_stderr(self):
        result = self._run(
            self._wrap(
                '{"jsonrpc":"2.0","id":1,"method":"pwsh",'
                '"params":{"command":{"id":"nope"}}}'
            )
        )
        self.assertIn("nope", result.stderr)

    def test_execution_failure_reports_to_stderr(self):
        result = self._run(
            self._wrap(
                '{"jsonrpc":"2.0","id":1,"method":"pwsh",'
                '"params":{"command":""}}'
            )
        )
        self.assertIn("request#1", result.stderr)

    def test_skill_failure_reports_to_stderr(self):
        result = self._run(
            self._wrap(
                '{"jsonrpc":"2.0","id":1,"method":"skill",'
                '"params":{"name":"no-such-skill-xyz"}}'
            )
        )
        self.assertIn("no-such-skill-xyz", result.stderr)

    def test_notification_failure_reports_to_stderr(self):
        # 无 id 的通知请求失败时不应被静默丢弃
        result = self._run(self._wrap('{"method":"bogus","params":{}}'))
        self.assertIn("bogus", result.stderr)

    def test_truncated_fence_reports_to_stderr(self):
        result = self._run("```chat2cli\n<request>\n" + '{"method":"pwsh"}' + "\n")
        self.assertIn("chat2cli", result.stderr)

    def test_bare_request_reports_to_stderr(self):
        result = self._run("<request>\n" + '{"method":"pwsh"}' + "\n</request>\n")
        self.assertIn("chat2cli", result.stderr)

    def test_skill_success_reports_to_stderr(self):
        # skill 成功激活也应有 stderr 回显，保持与其他方法一致
        import contextlib
        import io

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = os.path.join(tmpdir, "demo-skill")
            os.makedirs(skill_dir)
            with open(
                os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8"
            ) as f:
                f.write("demo body")
            old_skills = chat2cli._discovered_skills
            chat2cli._discovered_skills = {"demo-skill": {"path": skill_dir}}
            err = io.StringIO()
            try:
                with contextlib.redirect_stderr(err):
                    chat2cli.dispatch_request(
                        {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "skill",
                            "params": {"name": "demo-skill"},
                        },
                        {},
                    )
            finally:
                chat2cli._discovered_skills = old_skills
        self.assertIn("demo-skill", err.getvalue())


if __name__ == "__main__":
    unittest.main()

