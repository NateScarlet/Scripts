"""chat2cli.py 的提取逻辑单元测试。

重点覆盖：仅在 ```chat2cli 代码块内识别 <data.xxx> 和 <request> 标签；
代码块外的同名标签一律视为一般对话文本。
data 块内部的 <request> 属于字面内容，不应被当作 RPC 请求执行。
"""
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
        # data 块内容包含字面的 ``` 围栏时，外层使用四个反引号
        text = (
            "````chat2cli\n"
            "<data.code>\n"
            "```\n"
            "literal fence content\n"
            "```\n"
            "</data.code>\n"
            '<request>\n{"method":"skill"}\n</request>\n'
            "````"
        )
        blocks = chat2cli.extract_chat2cli_blocks(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["method"], "skill")
        data = chat2cli.extract_data_blocks(text)
        self.assertEqual(data["code"], "\n```\nliteral fence content\n```\n")

    def test_shorter_outer_fence_does_not_match_longer_close(self):
        # 外层围栏是三个反引号，内容包含四个反引号围栏时不应误解析
        text = (
            "```chat2cli\n"
            "<data.code>\n"
            "````\n"
            "literal fence content\n"
            "````\n"
            "</data.code>\n"
            "```"
        )
        blocks = chat2cli.extract_chat2cli_blocks(text)
        self.assertEqual(blocks, [])

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
    def test_detects_truncated_fence_with_literal_inner_fence(self):
        # 外层三反引号，data 块内含字面 ``` 围栏，导致外层围栏被提前截断
        text = (
            "```chat2cli\n"
            "<data.code>\n"
            "```\n"
            "literal fence content\n"
            "```\n"
            "</data.code>\n"
            '<request>\n{"method":"skill"}\n</request>\n'
            "```"
        )
        self.assertTrue(chat2cli.has_truncated_fence(text))

    def test_no_truncation_with_longer_outer_fence(self):
        # 外层四反引号，可以正常容纳内层 ``` 围栏
        text = (
            "````chat2cli\n"
            "<data.code>\n"
            "```\n"
            "literal fence content\n"
            "```\n"
            "</data.code>\n"
            '<request>\n{"method":"skill"}\n</request>\n'
            "````"
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


if __name__ == "__main__":
    unittest.main()
