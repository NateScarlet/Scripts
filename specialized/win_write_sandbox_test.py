
"""win_write_sandbox.py 的测试。

单元测试覆盖 SID 派生和拒绝检测；集成测试实际启动 pwsh 验证沙箱行为。
集成测试在非 Windows 或无法创建沙箱时跳过。
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import win_write_sandbox


class TestWorkspaceWriteSid(unittest.TestCase):
    def test_deterministic_for_same_path(self):
        path = os.getcwd()
        self.assertEqual(
            win_write_sandbox.workspace_write_sid(path),
            win_write_sandbox.workspace_write_sid(path),
        )

    def test_different_for_different_paths(self):
        base = tempfile.gettempdir()
        path_a = os.path.join(base, "chat2cli-sid-a")
        path_b = os.path.join(base, "chat2cli-sid-b")
        self.assertNotEqual(
            win_write_sandbox.workspace_write_sid(path_a),
            win_write_sandbox.workspace_write_sid(path_b),
        )

    def test_sid_format(self):
        sid = win_write_sandbox.workspace_write_sid(os.getcwd())
        self.assertTrue(sid.startswith("S-1-4-"))
        parts = sid.split("-")
        self.assertEqual(len(parts), 5)
        for part in parts[3:]:
            self.assertGreaterEqual(int(part), 1)
            self.assertLess(int(part), 2**30)


class TestDetectWriteDenial(unittest.TestCase):
    def test_recognizes_access_denied(self):
        msg = win_write_sandbox.detect_write_denial(
            "Remove-Item: Access is denied"
        )
        self.assertIsNotNone(msg)
        self.assertIn("只能写入工作目录", msg)
        self.assertIn("--danger-full-access", msg)

    def test_recognizes_unauthorized_access(self):
        msg = win_write_sandbox.detect_write_denial(
            "Exception: System.UnauthorizedAccessException"
        )
        self.assertIsNotNone(msg)

    def test_returns_none_for_normal_output(self):
        self.assertIsNone(win_write_sandbox.detect_write_denial("hello world"))

    def test_returns_none_for_empty(self):
        self.assertIsNone(win_write_sandbox.detect_write_denial(""))


@unittest.skipUnless(sys.platform == "win32", "仅 Windows")
class TestSandboxIntegration(unittest.TestCase):
    """实际启动 pwsh 验证沙箱读写边界。

    测试自包含：在 .scratch 下建立测试专用工作区，沙箱 cwd 指向它，
    其兄弟目录充当"工作区外"的目标，不触碰用户目录或其他仓库。
    """

    @classmethod
    def setUpClass(cls):
        base = os.path.join(os.getcwd(), ".scratch", "win-write-sandbox-test")
        cls.workspace = os.path.join(base, "workspace")
        cls.outside = os.path.join(base, "outside")
        os.makedirs(cls.workspace, exist_ok=True)
        os.makedirs(cls.outside, exist_ok=True)

    def _run(self, command: str, cwd: str = None, env: dict = None):
        return win_write_sandbox.spawn_pwsh_sandboxed(
            command,
            cwd or self.workspace,
            dict(os.environ) if env is None else env,
        )

    def _collect(self, proc):
        import threading
        out_lines, err_lines = [], []

        def reader(stream, sink):
            for line in iter(stream.readline, ""):
                sink.append(line)

        t1 = threading.Thread(
            target=reader, args=(proc.stdout, out_lines), daemon=True
        )
        t2 = threading.Thread(
            target=reader, args=(proc.stderr, err_lines), daemon=True
        )
        t1.start()
        t2.start()
        proc.wait()
        t1.join(timeout=5)
        t2.join(timeout=5)
        proc.close_handles()
        return "".join(out_lines), "".join(err_lines)

    def test_can_write_inside_workspace(self):
        target = os.path.join(self.workspace, "inside.txt")
        if os.path.exists(target):
            os.unlink(target)
        try:
            proc = self._run(
                f"Set-Content -Path '{target}' -Value 'ok' -Encoding utf8"
            )
            _, err = self._collect(proc)
            self.assertEqual(proc.returncode, 0, f"stderr: {err}")
            self.assertTrue(os.path.exists(target), "工作区内写入应成功")
        finally:
            if os.path.exists(target):
                os.unlink(target)

    def test_cannot_write_outside_workspace(self):
        """未受限上下文中，子进程获得全新沙箱，工作区外写入必须被拒绝。"""
        if win_write_sandbox.current_process_is_sandboxed():
            self.skipTest("当前进程已在沙箱内，子进程继承外层范围，测不出拒绝")
        target = os.path.join(self.outside, "denied.txt")
        if os.path.exists(target):
            os.unlink(target)
        try:
            proc = self._run(
                f"Set-Content -Path '{target}' -Value 'bad' -Encoding utf8"
            )
            _, err = self._collect(proc)
            self.assertFalse(
                os.path.exists(target), "工作区外的写入必须被拒绝"
            )
            self.assertNotEqual(
                proc.returncode, 0, "越权写入应以非零退出码失败"
            )
            self.assertIsNotNone(
                win_write_sandbox.detect_write_denial(err),
                f"stderr 应包含拒绝提示，实际: {err!r}",
            )
        finally:
            if os.path.exists(target):
                os.unlink(target)

    def test_nested_child_inherits_parent_write_access(self):
        """嵌套上下文中，子进程沿用父进程的可写范围，不再重新收窄。"""
        if not win_write_sandbox.current_process_is_sandboxed():
            self.skipTest("当前进程未受限，无继承语义可验证")
        target = os.path.join(self.outside, "nested.txt")
        if os.path.exists(target):
            os.unlink(target)
        try:
            proc = self._run(
                f"Set-Content -Path '{target}' -Value 'ok' -Encoding utf8"
            )
            _, err = self._collect(proc)
            self.assertEqual(proc.returncode, 0, f"stderr: {err}")
            self.assertTrue(
                os.path.exists(target), "子进程应保持父进程的可写范围"
            )
        finally:
            if os.path.exists(target):
                os.unlink(target)

    def test_cannot_delete_outside_workspace(self):
        """复现本次事故：对工作区外目录执行递归删除必须失败。"""
        if win_write_sandbox.current_process_is_sandboxed():
            self.skipTest("当前进程已在沙箱内，外层已授予该范围写权限")
        victim_dir = os.path.join(self.outside, "victim")
        os.makedirs(victim_dir, exist_ok=True)
        victim_file = os.path.join(victim_dir, "keep.txt")
        with open(victim_file, "w", encoding="utf-8") as f:
            f.write("must survive")
        try:
            proc = self._run(
                f"Remove-Item -Recurse -Force -ErrorAction Stop '{victim_dir}'"
            )
            _, err = self._collect(proc)
            self.assertTrue(
                os.path.exists(victim_file), "工作区外文件必须存活"
            )
            self.assertNotEqual(proc.returncode, 0)
        finally:
            import shutil
            shutil.rmtree(victim_dir, ignore_errors=True)

    def test_python_tempfile_works_in_sandbox(self):
        """注入启动钩子后，沙箱内 Python 的 tempfile 可正常创建与清理。"""
        hook_dir = win_write_sandbox.ensure_python_sitecustomize(
            os.path.join(self.workspace, ".hook")
        )
        tmp_dir = os.path.join(self.workspace, ".tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        helper = os.path.join(self.workspace, "tempfile_probe.py")
        with open(helper, "w", encoding="utf-8") as f:
            f.write(
                "import tempfile\n"
                "with tempfile.TemporaryDirectory() as d:\n"
                "    with open(d + '/x', 'w') as fp:\n"
                "        fp.write('x')\n"
                "print('tempfile ok')\n"
            )
        env = dict(os.environ)
        env["PYTHONPATH"] = hook_dir
        # TEMP 指向工作区内，使用例在沙箱内外运行都成立
        env["TEMP"] = tmp_dir
        env["TMP"] = tmp_dir
        # 带引号的路径需要 & 调用操作符，否则 PowerShell 会把它当作字符串字面量
        proc = self._run(f'& "{sys.executable}" "{helper}"', env=env)
        out, err = self._collect(proc)
        self.assertEqual(proc.returncode, 0, f"stderr: {err}")
        self.assertIn("tempfile ok", out)

    def test_invalid_cwd_raises(self):
        fake = os.path.join(self.workspace, "no-such-dir-xyz")
        self.assertFalse(os.path.exists(fake))
        with self.assertRaises(win_write_sandbox.SandboxError):
            self._run("echo hi", fake)


if __name__ == "__main__":
    unittest.main()

