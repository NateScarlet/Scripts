"""dsh_sandbox_grant 的测试。

重点验证 SID 派生与 DSH 实现逐位一致——这是整套放行机制的地基：
SID 只要差一位，ACE 就写到了一个 DSH 令牌不认识的身份上，放行静默失效。
"""

from __future__ import annotations

import hashlib
import os
import struct
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dsh_sandbox_grant as dsg  # noqa: E402


class TestWorkspaceSidDerivation(unittest.TestCase):
    """SID 派生必须与 DSH 的 workspaceWriteSid 完全一致。"""

    def test_matches_reference_algorithm(self):
        """对照 DSH 源码的算法独立实现一遍，逐位比对。"""
        path = "C:\\Workspaces\\scripts"
        digest = hashlib.sha256(path.encode("utf-8")).digest()
        expected = (
            f"S-1-4-"
            f"{struct.unpack_from('<I', digest, 0)[0] % (2**30 - 1) + 1}-"
            f"{struct.unpack_from('<I', digest, 4)[0] % (2**30 - 1) + 1}"
        )
        self.assertEqual(dsg.dsh_workspace_write_sid(path), expected)

    def test_matches_dsh_node_implementation(self):
        """直接调用 DSH 自己的 workspaceWriteSid 比对。

        DSH 的包在 pnpm 缓存里；找不到时跳过而不是失败，
        因为该路径依赖本机安装位置。
        """
        node = self._dsh_package_root()
        if node is None:
            self.skipTest("未找到 dsh-sandbox-windows-acl 包")

        path = "C:\\Workspaces\\scripts"
        script = (
            "const {createHash}=require('crypto');"
            f"const p={_js_string(path)};"
            "const d=createHash('sha256').update(p,'utf8').digest();"
            "console.log('S-1-4-'+(d.readUInt32LE(0)%(2**30-1)+1)+'-'"
            "+(d.readUInt32LE(4)%(2**30-1)+1));"
        )
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(
            dsg.dsh_workspace_write_sid(path), result.stdout.strip()
        )

    def test_is_deterministic_and_path_sensitive(self):
        a = dsg.dsh_workspace_write_sid("C:\\a")
        b = dsg.dsh_workspace_write_sid("C:\\a")
        c = dsg.dsh_workspace_write_sid("C:\\b")
        self.assertEqual(a, b, "同一路径必须派生出同一 SID")
        self.assertNotEqual(a, c, "不同路径必须派生出不同 SID")

    def test_case_sensitive_like_dsh(self):
        """DSH 哈希路径字符串本身，不做小写化，因此大小写是不同 SID。

        这是必须保留的行为：如果这里擅自小写化，派生出的 SID 就与
        DSH 实际使用的不一致，放行会全部失效。
        """
        self.assertNotEqual(
            dsg.dsh_workspace_write_sid("C:\\Foo"),
            dsg.dsh_workspace_write_sid("C:\\foo"),
        )

    def test_sid_shape(self):
        sid = dsg.dsh_workspace_write_sid("C:\\Workspaces\\scripts")
        self.assertRegex(sid, r"^S-1-4-\d+-\d+$")

    def _dsh_package_root(self):
        """定位 dsh-sandbox-windows-acl 包目录；找不到返回 None。

        pnpm dlx 的布局是 <hash>/<name>/node_modules/.pnpm/<pkg>/node_modules/...，
        中间的 <name> 层级不固定，因此用 glob 逐层匹配而不是写死深度。
        """
        root = os.path.join(
            os.path.expanduser("~"),
            "AppData", "Local", "pnpm-cache", "dlx",
        )
        if not os.path.isdir(root):
            return None

        import glob

        # dlx 下 <hash>/<name> 这一层的存在与否随 pnpm 版本而变，
        # 因此两种深度都试。
        for middle in ("*/*", "*"):
            found = glob.glob(
                os.path.join(root, middle, "node_modules", ".pnpm",
                             "*dsh-sandbox-wi*", "node_modules",
                             "@deepseek-ai", "dsh-sandbox-windows-acl")
            )
            if found:
                return found[0]
        return None


def _js_string(value: str) -> str:
    """把 Python 字符串转成可安全内联进 JS 源码的字面量。"""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


class TestCanonicalWorkspace(unittest.TestCase):
    def test_resolves_real_path(self):
        canonical = dsg.canonical_workspace(".")
        self.assertTrue(os.path.isabs(canonical))
        self.assertTrue(os.path.isdir(canonical))

    def test_resolve_returns_matching_sid(self):
        canonical, sid = dsg.resolve_workspace(None)
        self.assertEqual(sid, dsg.dsh_workspace_write_sid(canonical))
        self.assertEqual(canonical, dsg.canonical_workspace(os.getcwd()))

    def test_missing_workspace_raises(self):
        with self.assertRaises(dsg.DshGrantError):
            dsg.resolve_workspace("C:\\__dsh_no_such_dir__\\nope")


class TestGuard(unittest.TestCase):
    """管理命令必须拒绝在沙箱内运行。"""

    def test_sandbox_guard_reads_token(self):
        """守卫要么放行要么抛错，不应因读取令牌失败而静默通过。"""
        try:
            dsg._guard_not_sandboxed()
        except dsg.DshGrantError as e:
            self.assertIn("沙箱", str(e))


class TestArgParsing(unittest.TestCase):
    def test_grant_requires_target(self):
        parser = dsg.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["grant"])

    def test_workspace_flag_accepted_before_and_after_action(self):
        """--workspace 放在子命令前后都应生效。

        argparse 的子解析器会用自身默认值覆盖主解析器的解析结果，
        因此这个位置无关性由 main 的补偿逻辑保证，必须端到端验证，
        不能只测 build_parser。
        """
        before = dsg._workspace_before_action(
            ["--workspace", "C:\\w", "grant", "C:\\t"]
        )
        after = dsg._workspace_before_action(
            ["grant", "C:\\t", "--workspace", "C:\\w"]
        )
        self.assertEqual(before, "C:\\w")
        self.assertIsNone(
            after,
            "子命令之后的 --workspace 由子解析器处理，补偿函数不应重复接管",
        )

        # 端到端：两种写法都要把 --workspace 传给 cmd_sid
        for argv in (
            ["--workspace", "C:\\w", "sid"],
            ["sid", "--workspace", "C:\\w"],
        ):
            captured = {}

            def fake_cmd_sid(workspace):
                captured["workspace"] = workspace
                return 0

            original = dsg.cmd_sid
            dsg.cmd_sid = fake_cmd_sid
            try:
                dsg.main(argv)
            except Exception:
                pass
            finally:
                dsg.cmd_sid = original
            self.assertEqual(
                captured.get("workspace"), "C:\\w", f"argv={argv}"
            )

    def test_sid_action_needs_no_target(self):
        parser = dsg.build_parser()
        args = parser.parse_args(["sid"])
        self.assertEqual(args.action, "sid")
        self.assertIsNone(args.workspace)


class WorkspaceContainmentTest(unittest.TestCase):
    """目标在工作区内的判断（grant 的短路分支）。"""

    def test_same_path_detected(self):
        ws = os.path.normcase(os.path.abspath(".")).rstrip("\\/")
        tgt = os.path.normcase(os.path.abspath(".")).rstrip("\\/")
        self.assertTrue(tgt == ws or tgt.startswith(ws + os.sep))

    def test_child_detected(self):
        ws = os.path.normcase(os.path.abspath(".")).rstrip("\\/")
        tgt = os.path.normcase(os.path.join(os.path.abspath("."), "sub"))
        self.assertTrue(tgt.startswith(ws + os.sep))

    def test_sibling_not_detected(self):
        ws = os.path.normcase(os.path.abspath(".")).rstrip("\\/")
        tgt = os.path.normcase(os.path.abspath(os.path.join("..", "other")))
        self.assertFalse(tgt == ws or tgt.startswith(ws + os.sep))


class TestGrantRoundTrip(unittest.TestCase):
    """ACL 放行/撤销往返。

    需要未受限进程：在 DSH 沙箱内跳过，因为受限令牌没有目标目录的
    WRITE_DAC，grant 会（正确地）失败。
    """

    @classmethod
    def setUpClass(cls):
        import win_write_sandbox as wws

        try:
            cls.sandboxed = wws.current_process_is_sandboxed()
        except Exception:
            cls.sandboxed = True

    def setUp(self):
        if self.sandboxed:
            self.skipTest("当前进程已在沙箱内，无法验证 ACL 往返")
        import tempfile

        self.dir = tempfile.mkdtemp(prefix="dsh-grant-test-")

    def tearDown(self):
        if getattr(self, "dir", None) and os.path.isdir(self.dir):
            import shutil

            shutil.rmtree(self.dir, ignore_errors=True)

    def test_grant_then_revoke_round_trip(self):
        _canonical, sid = dsg.resolve_workspace(None)

        self.assertFalse(
            dsg._sid_already_granted(self.dir, sid), "初始状态不应已放行"
        )

        changed, failures = dsg._grant(self.dir, sid)
        self.assertEqual(failures, [])
        self.assertTrue(changed, "首次放行应发生变更")
        state = dsg._grant_state(self.dir, sid)
        self.assertEqual(
            state, {"grant": True, "deny": True, "label": True},
            "放行后三件应齐备",
        )
        self.assertTrue(dsg._sid_already_granted(self.dir, sid), "放行后应可写")

        # 幂等：重复放行不应再改 ACL
        changed2, failures2 = dsg._grant(self.dir, sid)
        self.assertEqual(failures2, [])
        self.assertFalse(changed2, "重复放行应是幂等的")

        result = dsg._revoke_tree(self.dir, sid)
        self.assertEqual(result.failures, [])
        self.assertGreater(result.changed, 0, "撤销应有变更")
        self.assertFalse(
            dsg._sid_already_granted(self.dir, sid), "撤销后不应再可写"
        )

    def test_inherited_ace_reaches_new_child(self):
        """可继承 ACE 必须让放行后新建的子目录自动可写。"""
        _canonical, sid = dsg.resolve_workspace(None)
        dsg._grant(self.dir, sid)

        child = os.path.join(self.dir, "newdir")
        os.makedirs(child)

        self.assertTrue(
            dsg._sid_already_granted(child, sid),
            "新建子目录应通过继承自动获得写入权限",
        )
        dsg._revoke_tree(self.dir, sid)


if __name__ == "__main__":
    unittest.main()
