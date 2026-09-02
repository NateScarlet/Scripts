"""chat2cli.py 的提取逻辑单元测试。

重点覆盖：识别 ```localrpc 代码块时应排除 <data.xxx> 块内部，
因为 data 块内容是字面文本，不应被当作 RPC 请求执行。
"""
import tempfile
import unittest
from pathlib import Path

import chat2cli


class TestExtractDataBlocks(unittest.TestCase):
    def test_simple(self):
        text = "<data.a>hello</data.a>"
        self.assertEqual(chat2cli.extract_data_blocks(text), {"a": "hello"})

    def test_multiline(self):
        text = "<data.code>\nline1\nline2\n</data.code>"
        self.assertEqual(
            chat2cli.extract_data_blocks(text), {"code": "\nline1\nline2\n"}
        )


class TestExtractChat2cliBlocks(unittest.TestCase):
    def test_normal_block(self):
        text = (
            '```localrpc\n'
            '{"jsonrpc":"2.0","id":1,"method":"skill","params":{"name":"x"}}\n'
            '```'
        )
        blocks = chat2cli.extract_chat2cli_blocks(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["method"], "skill")

    def test_skips_localrpc_inside_data_block(self):
        text = (
            "<data.example>\n"
            '```localrpc\n{"method":"pwsh"}\n```\n'
            "</data.example>\n"
            '```localrpc\n{"method":"skill"}\n```'
        )
        blocks = chat2cli.extract_chat2cli_blocks(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["method"], "skill")

    def test_update_initial_example_scenario(self):
        # data 块内容包含完整 localrpc 示例，字面内容不应被当作请求执行
        text = (
            "<data.example>\n"
            "```localrpc\n"
            '{"jsonrpc":"2.0","id":1,"method":"pwsh",'
            '"params":{"command":"Write-Output hi"}}\n'
            "```\n"
            "</data.example>"
        )
        blocks = chat2cli.extract_chat2cli_blocks(text)
        self.assertEqual(blocks, [])


class TestViewOobId(unittest.TestCase):
    def test_view_file_ref_id_uses_rpc_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            target = tmp / "example.txt"
            target.write_text("line1\nline2\n", encoding="utf-8")

            meta, content_block = chat2cli._view_file("42", str(target), {})

        self.assertTrue(meta["success"])
        self.assertEqual(meta["content"]["ref"], "view_42")
        self.assertTrue(content_block.startswith("<data.view_42>"))

    def test_view_directory_ref_id_uses_rpc_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            (tmp / "file.txt").write_text("x", encoding="utf-8")

            meta, content_block = chat2cli._view_directory("7", tmpdir)

        self.assertTrue(meta["success"])
        self.assertEqual(meta["content"]["ref"], "view_7")
        self.assertTrue(content_block.startswith("<data.view_7>"))


if __name__ == "__main__":
    unittest.main()
