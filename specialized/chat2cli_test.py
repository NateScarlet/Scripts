"""chat2cli.py 的提取逻辑单元测试。

重点覆盖：识别 ```localrpc 代码块时应排除 <data.xxx> 块内部，
因为 data 块内容是字面文本，不应被当作 RPC 请求执行。
"""
import unittest

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


if __name__ == "__main__":
    unittest.main()
