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
            "  <data.code>\n"
            "  ```\n"
            "  literal fence content\n"
            "  ```\n"
            "  </data.code>\n"
            '  <request>\n  {"method":"skill"}\n  </request>\n'
            "```"
        )
        blocks = chat2cli.extract_chat2cli_blocks(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["method"], "skill")
        data = chat2cli.extract_data_blocks(text)
        self.assertEqual(data["code"], "\n```\nliteral fence content\n```\n")

    def test_less_indented_line_raises_error(self):
        # 后续行缩进小于首行时，视为非法输入
        text = (
            "```chat2cli\n"
            "  <request>\n"
            '{"method":"skill"}\n'
            "  </request>\n"
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
    def test_does_not_detect_truncation_with_indented_literal_inner_fence(self):
        # 使用缩进处理含字面 ``` 围栏的 data 块，不应误判为截断
        text = (
            "```chat2cli\n"
            "  <data.code>\n"
            "  ```\n"
            "  literal fence content\n"
            "  ```\n"
            "  </data.code>\n"
            '  <request>\n  {"method":"skill"}\n  </request>\n'
            "```"
        )
        self.assertFalse(chat2cli.has_truncated_fence(text))

    def test_no_fence_at_all(self):
        text = "no fence here"
        self.assertFalse(chat2cli.has_truncated_fence(text))

    def test_valid_three_backtick_fence(self):
        # 正常的三反引号围栏，无截断
        text = (
            "```chat2cli\n"
            '<request>\n{"method":"skill"}\n</request>\n'
            "```"
        )
        self.assertFalse(chat2cli.has_truncated_fence(text))


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
                path = Path(result["path"])
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
            "  <request>\n"
            '{"method":"pwsh"}\n'
            "  </request>\n"
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


class TestEmitResultTextOobSelection(unittest.TestCase):
    """覆盖 OOB vs JSON 内联选择的阈值判断"""

    def setUp(self):
        chat2cli._pending_oob_data.clear()

    def _overhead(self, text: str, ref_id: str) -> int:
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


if __name__ == "__main__":
    unittest.main()
