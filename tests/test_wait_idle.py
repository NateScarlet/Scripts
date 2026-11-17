"""wait-idle.py 包裹模式的 pytest 测试。

通过 importlib 加载 lib/wait-idle.py（文件名含连字符，不能作为普通模块导入）。
所有外部依赖（时钟、休眠抑制、子进程、CPU 采样）均通过假实现注入。
"""

from __future__ import annotations

import importlib.util
import io
import queue
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Optional

import pytest

_MODULE_PATH = Path(__file__).resolve().parent.parent / "lib" / "wait-idle.py"
_spec = importlib.util.spec_from_file_location("wait_idle", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
wait_idle = importlib.util.module_from_spec(_spec)
sys.modules["wait_idle"] = wait_idle
_spec.loader.exec_module(wait_idle)


# #region 假实现

class FakeClock:
    """可推进的单调时钟，sleep 时按时间顺序触发已排程事件。"""

    def __init__(self, start_secs: float = 0.0):
        self._now_ns = int(start_secs * 1e9)
        self._events: list[tuple[int, Callable[[], None]]] = []
        self.sleep_calls: list[float] = []

    def now_ns(self) -> int:
        return self._now_ns

    def sleep(self, seconds: float) -> None:
        self.sleep_calls.append(seconds)
        target = self._now_ns + int(seconds * 1e9)
        while self._events and self._events[0][0] <= target:
            at_ns, callback = self._events.pop(0)
            self._now_ns = max(self._now_ns, at_ns)
            callback()
        self._now_ns = max(self._now_ns, target)

    def schedule(self, at_secs: float, callback: Callable[[], None]) -> None:
        self._events.append((int(at_secs * 1e9), callback))
        self._events.sort(key=lambda item: item[0])


class RealClock:
    """真实时钟，用于需要真实子进程的测试。"""

    def now_ns(self) -> int:
        return time.monotonic_ns()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


@dataclass
class FakeInhibitor:
    """记录 set_active 调用序列，不触碰真实系统 API。"""

    calls: list[bool] = field(default_factory=list)

    def set_active(self, active: bool) -> None:
        self.calls.append(active)


class FakeChild:
    """按时间脚本存活/退出的子进程替身。"""

    def __init__(self, clock: FakeClock, exit_at_secs: Optional[float] = None):
        self.clock = clock
        self.exit_at_ns = (
            int(exit_at_secs * 1e9) if exit_at_secs is not None else None
        )
        self.on_output: Optional[Callable[[], None]] = None
        self.interrupt_calls = 0
        self.kill_calls = 0
        self.waits: list[Optional[float]] = []
        self.wait_timeouts = 0
        self.exit_code = 0
        self.exited = False

    def poll(self) -> Optional[int]:
        if self.exited:
            return self.exit_code
        if self.exit_at_ns is not None and self.clock.now_ns() >= self.exit_at_ns:
            self.exited = True
            return self.exit_code
        return None

    def wait(self, timeout: Optional[float] = None) -> int:
        self.waits.append(timeout)
        if self.wait_timeouts > 0:
            self.wait_timeouts -= 1
            raise subprocess.TimeoutExpired("cmd", timeout or 0)
        self.clock.sleep(timeout or 0)
        self.exited = True
        return self.exit_code

    def send_interrupt(self) -> None:
        self.interrupt_calls += 1

    def kill(self) -> None:
        self.kill_calls += 1
        self.exited = True


def emit_output(child: FakeChild) -> None:
    assert child.on_output is not None
    child.on_output()


# #endregion


def make_fake_deps(
    clock: FakeClock,
    inhibitor: FakeInhibitor,
    child: FakeChild,
    cpu_sampler: Optional[Callable[[], Optional[float]]] = None,
) -> object:
    """构造包裹模式的假依赖容器。"""

    def spawn(command, *, on_output, stdout, stderr):
        child.on_output = on_output
        return child

    return wait_idle.WrapDeps(
        clock=clock,
        inhibitor=inhibitor,
        spawn=spawn,
        sample_child_cpu=cpu_sampler,
        stdout=sys.stdout.buffer,
        stderr=sys.stderr.buffer,
    )


# #region Slice A: 参数解析

def test_wrap_mode_uses_positional_as_window_and_keeps_command_verbatim():
    config = wait_idle.parse_cli(["5", "--", "cmd", "--child-cpu", "3", "arg"])
    assert config.wrap is True
    assert config.window_secs == 5
    assert config.command == ("cmd", "--child-cpu", "3", "arg")


def test_wrap_mode_without_window_defaults_to_60_seconds():
    config = wait_idle.parse_cli(["--", "cmd"])
    assert config.wrap is True
    assert config.window_secs == 60


def test_wait_mode_without_positional_defaults_to_600_seconds():
    config = wait_idle.parse_cli([])
    assert config.wrap is False
    assert config.duration_secs == 600
    assert config.command == ()


def test_wrap_mode_requires_command_after_separator():
    with pytest.raises(wait_idle.CLIArgumentError):
        wait_idle.parse_cli(["--"])


def test_missing_command_exits_2_without_spawning():
    clock = FakeClock()

    def forbidden_spawn(*args, **kwargs):
        raise AssertionError("不应启动子进程")

    deps = wait_idle.WrapDeps(
        clock=clock,
        inhibitor=FakeInhibitor(),
        spawn=forbidden_spawn,
        sample_child_cpu=None,
        stdout=sys.stdout.buffer,
        stderr=sys.stderr.buffer,
    )

    with pytest.raises(SystemExit) as exc:
        wait_idle.main(["--"], wrap_deps=deps)

    assert exc.value.code == 2


# #endregion


# #region Slice B: 子进程 I/O

def test_child_stdout_stderr_forwarded_verbatim():
    program = (
        "import sys;"
        "sys.stdout.buffer.write(b'out\\xff');"
        "sys.stderr.buffer.write(b'err\\n')"
    )
    stdout, stderr = io.BytesIO(), io.BytesIO()
    deps = wait_idle.WrapDeps(
        clock=RealClock(),
        inhibitor=FakeInhibitor(),
        spawn=wait_idle.spawn_child,
        sample_child_cpu=None,
        stdout=stdout,
        stderr=stderr,
    )

    with pytest.raises(SystemExit) as exc:
        wait_idle.main(
            ["--interval-secs", "0.01", "--", sys.executable, "-c", program],
            wrap_deps=deps,
        )

    assert exc.value.code == 0
    assert stdout.getvalue() == b"out\xff"
    assert stderr.getvalue() == b"err\n"


@pytest.mark.parametrize("child_code", [0, 7])
def test_child_exit_code_becomes_script_exit_code(child_code):
    deps = wait_idle.WrapDeps(
        clock=RealClock(),
        inhibitor=FakeInhibitor(),
        spawn=wait_idle.spawn_child,
        sample_child_cpu=None,
        stdout=io.BytesIO(),
        stderr=io.BytesIO(),
    )

    with pytest.raises(SystemExit) as exc:
        wait_idle.main(
            [
                "--interval-secs",
                "0.01",
                "--",
                sys.executable,
                "-c",
                f"import sys;sys.exit({child_code})",
            ],
            wrap_deps=deps,
        )

    assert exc.value.code == child_code


# #endregion


# #region Slice C: 休眠抑制按需切换

def test_child_with_no_output_is_active_only_during_startup_window():
    clock = FakeClock()
    child = FakeChild(clock, exit_at_secs=4)
    inhibitor = FakeInhibitor()
    deps = make_fake_deps(clock, inhibitor, child)

    with pytest.raises(SystemExit):
        wait_idle.main(["2", "--interval-secs", "1", "--", "cmd"], wrap_deps=deps)

    assert inhibitor.calls[0] is True
    assert inhibitor.calls[2] is True
    assert inhibitor.calls[3] is False
    assert inhibitor.calls[-1] is False


def test_window_expiry_releases_then_output_reacquires_inhibition():
    clock = FakeClock()
    child = FakeChild(clock, exit_at_secs=5)
    inhibitor = FakeInhibitor()
    clock.schedule(3.5, lambda: emit_output(child))
    deps = make_fake_deps(clock, inhibitor, child)

    with pytest.raises(SystemExit):
        wait_idle.main(["2", "--interval-secs", "1", "--", "cmd"], wrap_deps=deps)

    assert inhibitor.calls == [True, True, True, False, False, True, False]


def test_continuous_output_keeps_inhibition_on():
    clock = FakeClock()
    child = FakeChild(clock, exit_at_secs=4)
    inhibitor = FakeInhibitor()
    for at in (0.5, 1.5, 2.5, 3.5):
        clock.schedule(at, lambda: emit_output(child))
    deps = make_fake_deps(clock, inhibitor, child)

    with pytest.raises(SystemExit):
        wait_idle.main(["2", "--interval-secs", "1", "--", "cmd"], wrap_deps=deps)

    assert all(active is True for active in inhibitor.calls[:-1])
    assert inhibitor.calls[-1] is False


def test_cpu_above_threshold_keeps_inhibition_after_window_expiry():
    clock = FakeClock()
    child = FakeChild(clock, exit_at_secs=3)
    inhibitor = FakeInhibitor()
    deps = make_fake_deps(clock, inhibitor, child, lambda: 80.0)

    with pytest.raises(SystemExit):
        wait_idle.main(
            ["2", "--child-cpu", "50", "--interval-secs", "1", "--", "cmd"],
            wrap_deps=deps,
        )

    assert inhibitor.calls[3] is True


def test_cpu_below_threshold_releases_inhibition_after_window_expiry():
    clock = FakeClock()
    child = FakeChild(clock, exit_at_secs=3)
    inhibitor = FakeInhibitor()
    deps = make_fake_deps(clock, inhibitor, child, lambda: 10.0)

    with pytest.raises(SystemExit):
        wait_idle.main(
            ["2", "--child-cpu", "50", "--interval-secs", "1", "--", "cmd"],
            wrap_deps=deps,
        )

    assert inhibitor.calls[3] is False


def test_cpu_sampler_not_called_when_threshold_disabled():
    calls: list[int] = []

    def sampler():
        calls.append(1)
        return 100.0

    clock = FakeClock()
    child = FakeChild(clock, exit_at_secs=0.05)
    deps = make_fake_deps(clock, FakeInhibitor(), child, sampler)

    with pytest.raises(SystemExit):
        wait_idle.main(["--interval-secs", "0.01", "--", "cmd"], wrap_deps=deps)

    assert calls == []


def test_cpu_sampler_called_when_threshold_enabled():
    calls: list[int] = []

    def sampler():
        calls.append(1)
        return 10.0

    clock = FakeClock()
    child = FakeChild(clock, exit_at_secs=0.05)
    deps = make_fake_deps(clock, FakeInhibitor(), child, sampler)

    with pytest.raises(SystemExit):
        wait_idle.main(
            ["--child-cpu", "50", "--interval-secs", "0.01", "--", "cmd"],
            wrap_deps=deps,
        )

    assert calls


# #endregion


# #region Slice D: Ctrl+C 清理

def test_ctrl_c_interrupts_child_then_exits():
    clock = FakeClock()
    child = FakeChild(clock)
    inhibitor = FakeInhibitor()
    clock.schedule(0.5, lambda: (_ for _ in ()).throw(KeyboardInterrupt()))
    deps = make_fake_deps(clock, inhibitor, child)

    with pytest.raises(SystemExit) as exc:
        wait_idle.main(
            ["--interval-secs", "1", "--", "cmd"],
            wrap_deps=deps,
        )

    assert exc.value.code == 1
    assert child.interrupt_calls == 1
    assert child.kill_calls == 0
    assert child.exited is True
    assert inhibitor.calls[-1] is False


def test_ctrl_c_kills_child_that_ignores_interrupt():
    clock = FakeClock()
    child = FakeChild(clock)
    child.wait_timeouts = 1
    inhibitor = FakeInhibitor()
    clock.schedule(0.5, lambda: (_ for _ in ()).throw(KeyboardInterrupt()))
    deps = make_fake_deps(clock, inhibitor, child)

    with pytest.raises(SystemExit) as exc:
        wait_idle.main(
            ["--interval-secs", "1", "--", "cmd"],
            wrap_deps=deps,
        )

    assert exc.value.code == 1
    assert child.interrupt_calls == 1
    assert child.kill_calls == 1
    assert child.waits == [5.0, None]
    assert child.exited is True
    assert inhibitor.calls[-1] is False


# #endregion


# #region 真实依赖与回归

def test_sleep_inhibitor_only_calls_system_on_state_change():
    calls: list[bool] = []
    inhibitor = wait_idle.SleepInhibitor(set_state=lambda active: calls.append(active))

    inhibitor.set_active(True)
    inhibitor.set_active(True)
    inhibitor.set_active(False)
    inhibitor.set_active(False)

    assert calls == [True, False]


def test_real_cli_forwards_child_output_and_exit_code():
    result = subprocess.run(
        [
            sys.executable,
            str(_MODULE_PATH),
            "--interval-secs",
            "0.01",
            "--",
            sys.executable,
            "-c",
            "import sys;sys.stdout.buffer.write(b'hello');sys.exit(7)",
        ],
        capture_output=True,
        timeout=20,
    )

    assert result.returncode == 7
    assert result.stdout == b"hello"


def test_wait_mode_behavior_unchanged(monkeypatch):
    monkeypatch.setattr(wait_idle, "prevent_sleep", lambda: None)

    with pytest.raises(SystemExit) as exc:
        wait_idle.main(["0", "--ignore-user-input", "--interval-secs", "0.001"])

    assert exc.value.code == 0


def test_wait_mode_invalid_option_exits_two():
    with pytest.raises(SystemExit) as exc:
        wait_idle.main(["--cpu", "200"])

    assert exc.value.code == 2


# #endregion


# #region 审查修复回归

def test_wait_returns_even_when_forwarders_are_blocked():
    release = threading.Event()

    class BlockingSource:
        def read(self, size):
            release.wait(timeout=5)
            return b""

        def close(self):
            pass

    popen = SimpleNamespace(
        pid=1,
        stdout=BlockingSource(),
        stderr=BlockingSource(),
        wait=lambda timeout=None: 0,
        poll=lambda: 0,
        send_signal=lambda signal: None,
        kill=lambda: None,
    )
    handle = wait_idle.PopenChildHandle(popen)
    handle.start_forwarders(lambda: None, io.BytesIO(), io.BytesIO())

    result: list[int] = []
    runner = threading.Thread(target=lambda: result.append(handle.wait()))
    runner.start()
    runner.join(timeout=1.0)
    try:
        assert runner.is_alive() is False
        assert result == [0]
    finally:
        release.set()


def test_kill_terminates_whole_process_tree(monkeypatch):
    commands: list[list[str]] = []

    def fake_run(command, **kwargs):
        commands.append(list(command))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(wait_idle.subprocess, "run", fake_run)
    popen = SimpleNamespace(
        pid=4242,
        stdout=None,
        stderr=None,
        wait=lambda timeout=None: 0,
        poll=lambda: None,
        send_signal=lambda signal: None,
        kill=lambda: None,
    )
    handle = wait_idle.PopenChildHandle(popen)

    handle.kill()

    assert len(commands) == 1
    assert commands[0][0] == "taskkill"
    assert "/PID" in commands[0]
    assert "4242" in commands[0]
    assert "/T" in commands[0]
    assert "/F" in commands[0]


def test_zero_window_is_rejected():
    with pytest.raises(wait_idle.CLIArgumentError):
        wait_idle.parse_cli(["0", "--", "cmd"])


def test_child_output_arrives_before_child_exits():
    program = (
        "import sys,time;"
        "sys.stdout.write('MARK\\n');"
        "sys.stdout.flush();"
        "time.sleep(0.6)"
    )
    proc = subprocess.Popen(
        [
            sys.executable,
            str(_MODULE_PATH),
            "--interval-secs",
            "0.05",
            "--",
            sys.executable,
            "-c",
            program,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    arrived: queue.Queue = queue.Queue()
    start = time.monotonic()
    stdout = proc.stdout
    assert stdout is not None

    def drain() -> None:
        for _ in stdout:
            arrived.put(time.monotonic() - start)

    threading.Thread(target=drain, daemon=True).start()
    try:
        elapsed = arrived.get(timeout=0.3)
        assert elapsed < 0.3
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)


# #endregion
