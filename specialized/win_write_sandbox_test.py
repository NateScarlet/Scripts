
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


class TestGrantWriteSid(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(
            win_write_sandbox.grant_write_sid(),
            win_write_sandbox.grant_write_sid(),
        )

    def test_independent_of_workspace_sid(self):
        # 放行 SID 由用户 SID 派生，与 cwd 无关；工作区 SID 随 cwd 变化。
        self.assertNotEqual(
            win_write_sandbox.grant_write_sid(),
            win_write_sandbox.workspace_write_sid(os.getcwd()),
        )

    def test_sid_format(self):
        sid = win_write_sandbox.grant_write_sid()
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
        self.assertIn("sandbox grant", msg)
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

    def test_granted_directory_becomes_writable(self):
        """放行后工作区外目录可写，撤销后恢复拒绝。

        放行需要改 ACL（WRITE_DAC），在当前进程已被沙箱限制时必然失败，
        因此沙箱内运行时跳过。
        """
        if win_write_sandbox.current_process_is_sandboxed():
            self.skipTest("当前进程已受限，无法修改 ACL")

        grant_dir = os.path.join(
            os.getcwd(), ".scratch", "win-write-sandbox-test", "granted"
        )
        os.makedirs(grant_dir, exist_ok=True)
        target = os.path.join(grant_dir, "granted.txt")
        if os.path.exists(target):
            os.unlink(target)

        self.addCleanup(win_write_sandbox.revoke_write_access, grant_dir)
        win_write_sandbox.grant_write_access(grant_dir)

        command = f"Set-Content -Path '{target}' -Value 'ok'"
        out, err = self._collect(self._run(command))
        self.assertTrue(
            os.path.isfile(target),
            f"放行后应可写入，stdout={out!r} stderr={err!r}",
        )

        win_write_sandbox.revoke_write_access(grant_dir)
        os.unlink(target)
        _, err_after = self._collect(self._run(command))
        self.assertFalse(
            os.path.isfile(target),
            f"撤销后不应可写入，stderr={err_after!r}",
        )

    def test_granted_directory_propagates_to_existing_children(self):
        """放行靠目录的可继承 ACE 传播到已存在的子目录与文件。

        只对目录设置 ACE，其下已存在的子目录和文件无需逐个设置即可写。
        """
        if win_write_sandbox.current_process_is_sandboxed():
            self.skipTest("当前进程已受限，无法修改 ACL")

        grant_dir = os.path.join(
            os.getcwd(), ".scratch", "win-write-sandbox-test", "grant-tree"
        )
        sub = os.path.join(grant_dir, "sub")
        os.makedirs(sub, exist_ok=True)
        target = os.path.join(sub, "nested.txt")
        if os.path.exists(target):
            os.unlink(target)

        self.addCleanup(win_write_sandbox.revoke_write_access, grant_dir)
        win_write_sandbox.grant_write_access(grant_dir)

        command = f"Set-Content -Path '{target}' -Value 'ok'"
        out, err = self._collect(self._run(command))
        self.assertTrue(
            os.path.isfile(target),
            f"子目录中的文件应可写，stdout={out!r} stderr={err!r}",
        )

    def test_grant_sets_only_root_and_is_idempotent(self):
        """grant 只设置根目录一条显式 ACE，子项靠继承；重复调用幂等。"""
        if win_write_sandbox.current_process_is_sandboxed():
            self.skipTest("当前进程已受限，无法修改 ACL")

        grant_dir = os.path.join(
            os.getcwd(), ".scratch", "win-write-sandbox-test", "grant-root"
        )
        sub = os.path.join(grant_dir, "sub")
        os.makedirs(sub, exist_ok=True)
        self.addCleanup(win_write_sandbox.revoke_write_access, grant_dir)

        first = win_write_sandbox.grant_write_access(grant_dir)
        self.assertEqual(first.changed, 1)
        self.assertEqual(first.failures, [])

        status = win_write_sandbox.grant_status(grant_dir)
        # 只有根目录带显式 ACE，子目录靠继承可写
        self.assertEqual(status["explicit_entries"], [grant_dir])
        self.assertTrue(status["root_explicit"])
        self.assertEqual(status["writable_count"], status["total_count"])

        # 再次 grant：根目录已在放行范围内，不做任何修改
        second = win_write_sandbox.grant_write_access(grant_dir)
        self.assertEqual(second.changed, 0)
        self.assertEqual(second.failures, [])

    def test_grant_status_reflects_grant_and_revoke(self):
        """status 应准确反映放行状态，并列出含显式 ACE 的条目。"""
        if win_write_sandbox.current_process_is_sandboxed():
            self.skipTest("当前进程已受限，无法修改 ACL")

        grant_dir = os.path.join(
            os.getcwd(), ".scratch", "win-write-sandbox-test", "status-tree"
        )
        os.makedirs(grant_dir, exist_ok=True)
        self.addCleanup(win_write_sandbox.revoke_write_access, grant_dir)

        before = win_write_sandbox.grant_status(grant_dir)
        self.assertFalse(before["root_explicit"])
        self.assertEqual(before["explicit_entries"], [])

        win_write_sandbox.grant_write_access(grant_dir)
        after = win_write_sandbox.grant_status(grant_dir)
        self.assertTrue(after["root_explicit"])
        self.assertIn(grant_dir, after["explicit_entries"])

        win_write_sandbox.revoke_write_access(grant_dir)
        final = win_write_sandbox.grant_status(grant_dir)
        self.assertFalse(final["root_explicit"])
        self.assertEqual(final["explicit_entries"], [])

    def test_invalid_cwd_raises(self):
        fake = os.path.join(self.workspace, "no-such-dir-xyz")
        self.assertFalse(os.path.exists(fake))
        with self.assertRaises(win_write_sandbox.SandboxError):
            self._run("echo hi", fake)


if __name__ == "__main__":
    unittest.main()

