"""
wait-idle.py - 等待系统空闲的等待脚本

该脚本持续等待系统资源使用情况，直到CPU和GPU占用率持续低于阈值达到指定时间后才退出。
适用于挂机渲染任务完成后的等待场景。
空闲持续时间从第一次获取有效监控数据后开始计算，最少运行一个周期。

使用示例:
  # 基本用法
  python wait-idle.py && echo system-idle

  # 详细输出模式
  python wait-idle.py --verbose && echo system-idle

  # 包裹模式：运行指定程序，只在它活跃时阻止休眠
  python wait-idle.py 60 -- <command> [args...]

包裹模式下，-- 之后的参数原样作为子进程命令。位置参数为 stdio 闲置窗口
（秒，默认 60）：子进程在该窗口内产生过输出、或子进程树 CPU 超过 --child-cpu
阈值时阻止休眠，否则释放抑制；子进程退出脚本即退出，退出码原样透传。

退出代码:
  0 - 成功达到目标空闲时间
  1 - 等待过程中出现错误或用户中断
  2 - 参数错误
  包裹模式下为子进程的退出码
"""

# pyright: standard

import sys
import time
import logging
import argparse
import ctypes
import os
import signal
import subprocess
import threading
from abc import ABC, abstractmethod
from contextlib import ExitStack
from contextlib import contextmanager
from dataclasses import dataclass
from typing import BinaryIO, Iterator, Optional, Callable, Protocol, Sequence

from tqdm import tqdm

_LOGGER = logging.getLogger(__name__)

# 收到中断后留给子进程自行退出的宽限期，超时才强制结束
INTERRUPT_GRACE_SECS = 5.0

# 子进程退出后等待输出转发线程排空的时间；孙进程持有管道时不无限等待
FORWARD_DRAIN_SECS = 0.2

# Windows API 相关导入
try:
    import win32api
    import win32pdh
    import pythoncom
except ImportError:
    win32api = None
    win32pdh = None
    pythoncom = None

class BaseChecker(ABC):
    """
    空闲状态检查器基类
    """

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def update(self, now_ns: int, last_tick_ns: int):
        """执行检查器更新（如采集数据）"""
        pass

    @abstractmethod
    def is_ok(self) -> bool:
        """返回当前是否处于空闲状态"""
        pass

    @abstractmethod
    def status_text(self) -> str:
        """返回当前状态的描述文本，用于日志"""
        pass

    @abstractmethod
    def threshold_text(self) -> str:
        """返回阈值的描述文本，用于日志"""
        pass


class ThresholdChecker(BaseChecker):
    """
    基于阈值的数值检查器
    """

    def __init__(
        self,
        name: str,
        get_usage: Callable[[], Optional[float]],
        threshold: float,
        unit: str = "%",
    ):
        super().__init__(name)
        self.get_usage = get_usage
        self.threshold = threshold
        self.unit = unit
        self._current_value = None

    def update(self, now_ns: int, last_tick_ns: int):
        self._current_value = self.get_usage()

    def is_ok(self) -> bool:
        if self._current_value is None:
            return True
        return self._current_value <= self.threshold

    def status_text(self) -> str:
        val = (
            f"{self._current_value:.1f}{self.unit}"
            if self._current_value is not None
            else "N/A"
        )
        return f"{self.name}: {val}"

    def threshold_text(self) -> str:
        return f"{self.name} ≤ {self.threshold}{self.unit}"


class InputChecker(BaseChecker):
    """
    用户输入检查器
    """

    def __init__(self, get_since_last_input_ns: Callable[[], Optional[int]]):
        super().__init__("用户输入")
        self.get_since_last_input_ns = get_since_last_input_ns
        self._since_last_input_ns = None
        self._now_ns = None
        self._last_tick_ns = None
        self._not_ok_count = 0
        self._warning_sent = False
        self._has_been_idle = False

    def update(self, now_ns: int, last_tick_ns: int):
        self._since_last_input_ns = self.get_since_last_input_ns()
        self._now_ns = now_ns
        self._last_tick_ns = last_tick_ns

        # 启动诊断逻辑：仅在首次确认闲置前进行一次性检查
        if self._has_been_idle or self._since_last_input_ns is None:
            return

        if self.is_ok():
            _LOGGER.info("✅ 正常检测到用户停止输入")
            self._has_been_idle = True
            return

        self._not_ok_count += 1
        if not self._warning_sent and self._not_ok_count >= 3:
            _LOGGER.warning(
                "⚠️ 检测到持续的用户输入已超过 3 个检测周期。如果并非人工操作，可能某个设备（如模拟鼠标、键鼠宏或损坏的设备）在持续自动发送输入，这将导致无法进入空闲状态。建议检查设备或使用 --ignore-user-input 选项。"
            )
            self._warning_sent = True

    def is_ok(self) -> bool:
        if self._since_last_input_ns is None:
            return True
        # 需要距离上次操作的时间大于检测间隔，才认为本周期是空闲的
        return self._since_last_input_ns >= (self._now_ns - self._last_tick_ns)

    def status_text(self) -> str:
        val = (
            f"{self._since_last_input_ns/1e9:.3f}秒前"
            if self._since_last_input_ns is not None
            else "N/A"
        )
        return f"距上次操作: {val}"

    def threshold_text(self) -> str:
        return "用户无操作"


class CPUMonitor:
    """CPU 监控类，使用 Windows Performance Counter API"""

    def __init__(self):
        assert pythoncom
        assert win32pdh

        self._query_handle = None
        self._counter_handle = None
        self._com_initialized = False
        self._last_value = None

        # 初始化 COM
        pythoncom.CoInitialize()
        self._com_initialized = True

        # 创建 PDH 查询
        self._query_handle = win32pdh.OpenQuery()
        counter_path = r"\Processor(_Total)\% Processor Time"
        self._counter_handle = win32pdh.AddCounter(self._query_handle, counter_path)

        # 收集初始数据
        win32pdh.CollectQueryData(self._query_handle)
        time.sleep(0.1)  # 等待一段时间以获取有效数据
        win32pdh.CollectQueryData(self._query_handle)
        self._last_collect_time_ns = time.monotonic_ns()
        data = win32pdh.GetFormattedCounterValue(
            self._counter_handle, win32pdh.PDH_FMT_DOUBLE
        )
        self._last_value = data[1] if data[1] is not None else 0.0

        _LOGGER.debug("CPU 监控初始化完成")

    def get_usage(self) -> Optional[float]:
        """获取 CPU 总使用率（百分比）"""
        if not self._query_handle or not self._counter_handle:
            return None

        assert win32pdh
        current_time_ns = time.monotonic_ns()
        win32pdh.CollectQueryData(self._query_handle)

        try:
            data = win32pdh.GetFormattedCounterValue(
                self._counter_handle, win32pdh.PDH_FMT_DOUBLE
            )
        except win32pdh.error as e:
            if e.winerror not in _IGNORE_PDH_ERRORS:
                _LOGGER.exception("获取 CPU 使用率出错，视为不可用")
            return 1.0
        current_value = data[1] if data[1] is not None else 0.0

        # 计算两次采集的时间间隔
        time_diff_ns = current_time_ns - self._last_collect_time_ns
        if time_diff_ns <= 0:
            return self._last_value

        # 更新最后的数据
        self._last_collect_time_ns = current_time_ns
        self._last_value = current_value

        return current_value

    def cleanup(self):
        """清理资源"""
        if self._counter_handle:
            try:
                assert win32pdh
                win32pdh.RemoveCounter(self._counter_handle)
            except Exception:
                pass
            self._counter_handle = None

        if self._query_handle:
            try:
                assert win32pdh
                win32pdh.CloseQuery(self._query_handle)
            except Exception:
                pass
            self._query_handle = None

        if self._com_initialized:
            try:
                assert pythoncom
                pythoncom.CoUninitialize()
            except Exception:
                pass
            self._com_initialized = False


PDH_CSTATUS_INVALID_DATA = -1073738822
_IGNORE_PDH_ERRORS = (PDH_CSTATUS_INVALID_DATA,)


class GPUMonitor:
    """GPU 监控类，使用 Windows Performance Counter API"""

    def __init__(self):
        assert pythoncom

        self._query_handle = None
        self._counter_handle = None
        self._com_initialized = False
        self._method = None
        self._last_running_times = {}  # 用于 running_time 方法
        self._last_collect_time_ns = None

        # 初始化 COM
        pythoncom.CoInitialize()
        self._com_initialized = True

        # 尝试不同的计数器路径
        counter_methods = [
            (r"\GPU Engine(*)\Utilization Percentage", "percentage"),
            (r"\GPU Engine(*engtype_3D)\Utilization Percentage", "percentage_3d"),
            (r"\GPU Engine(*)\Running Time", "running_time"),
        ]

        for counter_path, method_type in counter_methods:
            if self._try_counter(counter_path, method_type):
                self._method = method_type
                _LOGGER.debug(
                    f"使用 GPU 监控方法: {counter_path} (方法: {method_type})"
                )
                break
        else:
            self.cleanup()
            raise RuntimeError("没有可用 GPU 监控方法")

    def _try_counter(self, counter_path: str, method_type: str) -> bool:
        """尝试使用指定的计数器路径"""
        assert win32pdh
        query_handle = None
        try:
            query_handle = win32pdh.OpenQuery()
            counter_handle = win32pdh.AddCounter(query_handle, counter_path)

            # 测试计数器是否可用
            win32pdh.CollectQueryData(query_handle)
            time.sleep(0.1)
            win32pdh.CollectQueryData(query_handle)

            # 尝试获取数据
            if method_type == "running_time":
                data: dict = win32pdh.GetFormattedCounterArray(
                    counter_handle, win32pdh.PDH_FMT_LARGE
                )
            else:
                data: dict = win32pdh.GetFormattedCounterArray(
                    counter_handle, win32pdh.PDH_FMT_DOUBLE
                )

            if data and any(i is not None for i in data.values()):
                self._query_handle = query_handle
                self._counter_handle = counter_handle
                return True

            win32pdh.CloseQuery(query_handle)
            return False

        except Exception as e:
            if query_handle:
                try:
                    win32pdh.CloseQuery(query_handle)
                except Exception:
                    pass
            _LOGGER.debug(f"GPU 计数器 {counter_path} 不可用: {e}")
            return False

    def get_usage(self) -> Optional[float]:
        """获取 GPU 使用率（百分比）"""
        if not self._query_handle or not self._method:
            return None

        if self._method == "running_time":
            return self._get_usage_by_running_time()
        else:
            return self._get_usage_by_percentage()

    def _get_usage_by_percentage(self) -> Optional[float]:
        """通过百分比计数器获取 GPU 使用率"""
        if not self._query_handle or not self._counter_handle:
            return None

        assert win32pdh
        win32pdh.CollectQueryData(self._query_handle)

        try:
            items: dict = win32pdh.GetFormattedCounterArray(
                self._counter_handle, win32pdh.PDH_FMT_DOUBLE
            )
        except win32pdh.error as e:
            if e.winerror not in _IGNORE_PDH_ERRORS:
                _LOGGER.exception("获取 GPU 使用率出错，视为不可用")
            return 1.0

        max_usage = 0.0
        for _, usage in items.items():
            if usage is not None and isinstance(usage, (int, float)):
                usage_float = float(usage)
                if usage_float > max_usage:
                    max_usage = usage_float

        return max_usage

    def _get_usage_by_running_time(self) -> Optional[float]:
        """通过运行时间计数器获取 GPU 使用率"""
        if not self._query_handle or not self._counter_handle:
            return None

        assert win32pdh
        current_time_ns = time.monotonic_ns()
        win32pdh.CollectQueryData(self._query_handle)

        try:
            items: dict = win32pdh.GetFormattedCounterArray(
                self._counter_handle, win32pdh.PDH_FMT_LARGE
            )
        except win32pdh.error as e:
            if e.winerror not in _IGNORE_PDH_ERRORS:
                _LOGGER.exception("获取 GPU 使用率出错，视为不可用")
            return 1.0

        current_running_times = {}

        # 收集当前运行时间
        for name, running_time in items.items():
            if running_time is not None and name:
                current_running_times[name] = running_time

        # 如果是第一次收集，保存数据并返回 0
        if self._last_collect_time_ns is None or not self._last_running_times:
            self._last_collect_time_ns = current_time_ns
            self._last_running_times = current_running_times
            return 0.0

        # 计算时间差
        time_diff_ns = current_time_ns - self._last_collect_time_ns
        if time_diff_ns <= 0:
            return 0.0

        # 计算每个 GPU 引擎的使用率
        max_usage = 0.0
        for name, current_time_val in current_running_times.items():
            if name in self._last_running_times:
                last_time_val = self._last_running_times[name]
                if current_time_val > last_time_val:
                    # 运行时间增量（100纳秒单位）转换为纳秒
                    running_time_diff_ns = (current_time_val - last_time_val) / 100
                    usage_percent = running_time_diff_ns / time_diff_ns * 100
                    if usage_percent > max_usage:
                        max_usage = usage_percent

        # 更新最后的数据
        self._last_collect_time_ns = current_time_ns
        self._last_running_times = current_running_times

        return max_usage

    def cleanup(self):
        """清理资源"""
        if self._query_handle:
            try:
                assert win32pdh
                win32pdh.CloseQuery(self._query_handle)
            except Exception:
                pass
            self._query_handle = None
            self._counter_handle = None

        if self._com_initialized:
            try:
                assert pythoncom
                pythoncom.CoUninitialize()
            except Exception:
                pass
            self._com_initialized = False


class VRAMMonitor:
    """显存监控类，使用 Windows Performance Counter API"""

    def __init__(self):
        assert pythoncom
        assert win32pdh

        self._query_handle = None
        self._counter_handle = None
        self._com_initialized = False

        # 初始化 COM
        pythoncom.CoInitialize()
        self._com_initialized = True

        # 创建 PDH 查询
        self._query_handle = win32pdh.OpenQuery()
        # 使用 Dedicated Usage 计数器获取专用显存占用情况
        counter_path = r"\GPU Adapter Memory(*)\Dedicated Usage"
        try:
            self._counter_handle = win32pdh.AddCounter(self._query_handle, counter_path)
            # 收集初始数据
            win32pdh.CollectQueryData(self._query_handle)
        except Exception as e:
            self.cleanup()
            raise RuntimeError(f"无法初始化显存监控: {e}")

    def get_usage_mb(self) -> Optional[float]:
        """获取所有显卡显存占用总量（MB）"""
        if not self._query_handle or not self._counter_handle:
            return None

        assert win32pdh
        try:
            win32pdh.CollectQueryData(self._query_handle)
            items: dict = win32pdh.GetFormattedCounterArray(
                self._counter_handle, win32pdh.PDH_FMT_LARGE
            )
        except win32pdh.error as e:
            if e.winerror not in _IGNORE_PDH_ERRORS:
                _LOGGER.exception("获取显存使用量出错")
            return None

        if not items:
            return 0.0

        total_bytes = 0
        for usage in items.values():
            if usage is not None:
                total_bytes += usage

        return total_bytes / (1024 * 1024)

    @staticmethod
    def get_total_vram_mb() -> float:
        """获取系统总专用显存 (MB)"""
        import subprocess

        # 1. 尝试使用 nvidia-smi (更准确，能处理 >4GB 显存)
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=2
            )
            total = 0.0
            for line in out.splitlines():
                if line.strip():
                    total += float(line.strip())
            if total > 0:
                return total
        except Exception:
            pass

        # 2. 尝试使用 PowerShell (兼容性更好，但大显存可能被截断为 4GB)
        try:
            # 通过 PowerShell 获取各显卡的 AdapterRAM (单位：字节)
            cmd = ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty AdapterRAM"]
            output = subprocess.check_output(cmd, text=True, timeout=5, stderr=subprocess.DEVNULL).strip()
            total_bytes = 0
            for line in output.splitlines():
                try:
                    val = int(line)
                    # 处理可能的 32 位符号溢出
                    if val < 0:
                        val += 2 ** 32
                    total_bytes += val
                except ValueError:
                    continue
            return total_bytes / (1024 * 1024)
        except Exception:
            return 0.0

    def cleanup(self):
        """清理资源"""
        if self._counter_handle:
            try:
                assert win32pdh
                win32pdh.RemoveCounter(self._counter_handle)
            except Exception:
                pass
            self._counter_handle = None

        if self._query_handle:
            try:
                assert win32pdh
                win32pdh.CloseQuery(self._query_handle)
            except Exception:
                pass
            self._query_handle = None

        if self._com_initialized:
            try:
                assert pythoncom
                pythoncom.CoUninitialize()
            except Exception:
                pass
            self._com_initialized = False


def get_cpu_monitor_func(
    stack: ExitStack,
    cpu_threshold: float,
) -> Callable[[], Optional[float]]:
    """
    返回获取 CPU 使用率的函数
    """
    # 如果阈值为 100，表示忽略 CPU
    if cpu_threshold == 100:
        return lambda: None

    # 检查 Windows API 是否可用
    if not all([win32pdh, pythoncom]):
        _LOGGER.warning("CPU 监控不可用: 需要 pywin32 库，将忽略 CPU 阈值")
        return lambda: None

    # 尝试创建 CPU 监控器
    try:
        monitor = CPUMonitor()
        stack.callback(monitor.cleanup)
        return monitor.get_usage
    except Exception as e:
        _LOGGER.warning(f"CPU 监控初始化失败: {e}，将忽略 CPU 阈值")
        return lambda: None


def get_gpu_monitor_func(
    stack: ExitStack,
    gpu_threshold: float,
) -> Callable[[], Optional[float]]:
    """
    返回获取 GPU 使用率的函数
    """
    # 如果阈值为 100，表示忽略 GPU
    if gpu_threshold == 100:
        return lambda: None

    # 检查 Windows API 是否可用
    if not all([win32pdh, pythoncom]):
        _LOGGER.warning("GPU 监控不可用: 需要 pywin32 库，将忽略 GPU 阈值")
        return lambda: None

    # 尝试创建 GPU 监控器
    try:
        monitor = GPUMonitor()
        stack.callback(monitor.cleanup)
        return monitor.get_usage
    except RuntimeError:
        _LOGGER.warning("未找到可用的 GPU 计数器，将忽略 GPU 阈值")
        return lambda: None


def get_vram_monitor_func(
    stack: ExitStack,
    vram_threshold: Optional[float],
) -> Callable[[], Optional[float]]:
    """
    返回获取显存使用率 (MB) 的函数
    """
    # 如果阈值为 None，表示忽略显存
    if vram_threshold is None:
        return lambda: None

    # 检查 Windows API 是否可用
    if not all([win32pdh, pythoncom]):
        _LOGGER.warning("显存监控不可用: 需要 pywin32 库，将忽略显存阈值")
        return lambda: None

    # 尝试创建显存监控器
    try:
        monitor = VRAMMonitor()
        stack.callback(monitor.cleanup)
        return monitor.get_usage_mb
    except Exception as e:
        _LOGGER.warning(f"显存监控初始化失败: {e}，将忽略显存阈值")
        return lambda: None


def prevent_sleep():
    """
    阻止系统进入睡眠状态
    """
    if ctypes:
        ES_CONTINUOUS = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        )


def get_since_last_input_ns() -> Optional[int]:
    if win32api:
        last_input = win32api.GetLastInputInfo()  # 用户最后一次输入时间（会溢出）
        current_uptime = win32api.GetTickCount()  # 当前系统运行时间（会溢出）
        idle_ms = (current_uptime - last_input) % 0x100000000  # 处理回绕
        return idle_ms * 1_000_000


def precise_ticker(interval_ns: int, immediate: bool) -> Iterator[int]:
    next_time = time.monotonic_ns() + (0 if immediate else interval_ns)
    while True:
        current_time = time.monotonic_ns()

        if current_time >= next_time:
            # 已经超时，立即 yield
            yield current_time
            # 重新开始计时
            next_time = current_time + interval_ns
        else:
            # 计算剩余时间并 sleep
            sleep_time = next_time - current_time
            time.sleep(sleep_time / 1e9)
            # sleep 结束后再 yield
            yield time.monotonic_ns()
            next_time += interval_ns


class CLIArgumentError(Exception):
    """命令行参数错误。"""


@dataclass(frozen=True)
class CLIConfig:
    """解析后的命令行配置。"""

    wrap: bool
    command: tuple[str, ...]
    duration_secs: float
    window_secs: float
    child_cpu_threshold: Optional[float]
    cpu_threshold: float
    gpu_threshold: float
    vram_threshold: Optional[float]
    interval_secs: float
    ignore_user_input: bool
    verbose: bool


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="等待系统空闲持续指定时间；使用 -- 包裹子进程时按子进程活跃度抑制休眠",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "duration_secs",
        nargs="?",
        type=float,
        default=None,
        help="空闲等待时长（秒）；包裹模式下为 stdio 闲置窗口（默认 60）",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="启用详细输出模式")
    parser.add_argument(
        "--ignore-user-input",
        action="store_true",
        help="忽略用户输入（用户正在操作也可进入空闲状态）",
    )
    # 正常渲染任务都是占满的，阈值设太低可能光后台任务都视为非空闲了
    # XXX: 闲置时CPU占用率比资源管理器看到的要高，不知原因，测试满载时都是100%
    parser.add_argument("--cpu", type=float, default=50, help="CPU阈值")
    parser.add_argument("--gpu", type=float, default=50, help="GPU阈值")
    parser.add_argument("--vram", type=float, default=None, help="显存占用阈值(MB)")
    parser.add_argument("--interval-secs", type=float, default=1.0, help="检测间隔(秒)")
    parser.add_argument(
        "--child-cpu",
        type=float,
        default=None,
        help="子进程树 CPU 占用阈值(百分比)，默认关闭",
    )
    return parser


def parse_cli(argv: Optional[Sequence[str]] = None) -> CLIConfig:
    """解析命令行；-- 之后的参数原样作为子进程命令。"""
    raw = list(sys.argv[1:] if argv is None else argv)
    if "--" in raw:
        separator = raw.index("--")
        head = raw[:separator]
        command = tuple(raw[separator + 1 :])
        if not command:
            raise CLIArgumentError("-- 之后必须指定要运行的命令")
        wrap = True
    else:
        head = raw
        command = ()
        wrap = False

    args = build_parser().parse_args(head)
    if wrap:
        window_secs = 60.0 if args.duration_secs is None else args.duration_secs
        duration_secs = 600.0
    else:
        duration_secs = 600.0 if args.duration_secs is None else args.duration_secs
        window_secs = 60.0

    # 参数错误在可信边界统一拦截，退出码约定为 2
    if duration_secs < 0 or window_secs <= 0:
        raise CLIArgumentError("等待时间不能为负数，stdio 闲置窗口必须大于 0")
    if not (0 <= args.cpu <= 100):
        raise CLIArgumentError("CPU 阈值应该为 0-100")
    if not (0 <= args.gpu <= 100):
        raise CLIArgumentError("GPU 阈值应该为 0-100")
    if args.vram is not None and args.vram < 0:
        raise CLIArgumentError("VRAM 阈值不能为负数")
    if not (int(args.interval_secs * 1e9) > 0):
        raise CLIArgumentError("检测间隔应该大于 0")
    if args.child_cpu is not None and not (0 <= args.child_cpu <= 100):
        raise CLIArgumentError("子进程 CPU 阈值应该为 0-100")

    return CLIConfig(
        wrap=wrap,
        command=command,
        duration_secs=duration_secs,
        window_secs=window_secs,
        child_cpu_threshold=args.child_cpu,
        cpu_threshold=args.cpu,
        gpu_threshold=args.gpu,
        vram_threshold=args.vram,
        interval_secs=args.interval_secs,
        ignore_user_input=args.ignore_user_input,
        verbose=args.verbose,
    )


class ClockLike(Protocol):
    def now_ns(self) -> int: ...

    def sleep(self, seconds: float) -> None: ...


class SleepInhibitorLike(Protocol):
    def set_active(self, active: bool) -> None: ...


class ChildHandleLike(Protocol):
    def poll(self) -> Optional[int]: ...

    def wait(self, timeout: Optional[float] = None) -> int: ...

    def send_interrupt(self) -> None: ...

    def kill(self) -> None: ...


@dataclass
class WrapDeps:
    """包裹模式的可注入依赖。"""

    clock: ClockLike
    inhibitor: SleepInhibitorLike
    spawn: Callable[..., ChildHandleLike]
    sample_child_cpu: Optional[Callable[[], Optional[float]]]
    stdout: BinaryIO
    stderr: BinaryIO


class PopenChildHandle:
    """subprocess.Popen 的包装，统一暴露包裹模式需要的进程操作。"""

    FORWARD_CHUNK_SIZE = 4096

    def __init__(self, popen: subprocess.Popen):
        self._popen = popen
        self._forwarders: list[threading.Thread] = []

    def start_forwarders(self, on_output, stdout, stderr) -> None:
        sources = ((self._popen.stdout, stdout), (self._popen.stderr, stderr))
        for source, target in sources:
            if source is None:
                continue
            thread = threading.Thread(
                target=self._forward,
                args=(source, target, on_output),
                daemon=True,
            )
            thread.start()
            self._forwarders.append(thread)

    @classmethod
    def _forward(cls, source, target, on_output) -> None:
        """按原始字节实时转发，不解码、不加前缀、不改换行。"""
        # read(n) 会等到读满 n 字节或 EOF 才返回，小量输出要等到子进程退出才可见；
        # read1(n) 只要有数据就返回，保证转发实时。
        read_chunk = getattr(source, "read1", source.read)
        try:
            while True:
                chunk = read_chunk(cls.FORWARD_CHUNK_SIZE)
                if not chunk:
                    break
                target.write(chunk)
                target.flush()
                on_output()
        finally:
            source.close()

    @property
    def pid(self) -> int:
        return self._popen.pid

    def poll(self) -> Optional[int]:
        return self._popen.poll()

    def wait(self, timeout: Optional[float] = None) -> int:
        code = self._popen.wait(timeout=timeout)
        # 孙进程可能继承管道导致转发线程读不到 EOF，限时排空后立即返回
        for thread in self._forwarders:
            thread.join(timeout=FORWARD_DRAIN_SECS)
        return code

    def send_interrupt(self) -> None:
        if sys.platform == "win32":
            self._popen.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            self._popen.send_signal(signal.SIGINT)

    def kill(self) -> None:
        # 必须结束整棵进程树，只杀根进程会留下持有管道的孙进程
        if sys.platform == "win32":
            result = subprocess.run(
                ["taskkill", "/PID", str(self.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=INTERRUPT_GRACE_SECS,
            )
            if result.returncode != 0:
                self._popen.kill()
        else:
            try:
                os.killpg(os.getpgid(self.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                self._popen.kill()


def spawn_child(command, *, on_output, stdout, stderr) -> PopenChildHandle:
    """启动子进程并按原始字节转发 stdout/stderr，stdin 直接继承。"""
    kwargs = {}
    if sys.platform == "win32":
        # 独立进程组，才能单独向子进程发送中断而不影响脚本自身
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    popen = subprocess.Popen(
        list(command),
        stdin=None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **kwargs,
    )
    handle = PopenChildHandle(popen)
    handle.start_forwarders(on_output, stdout, stderr)
    return handle


class ActivityTracker:
    """根据启动阶段与 stdio 输出事件判断子进程是否活跃。"""

    def __init__(self, clock, window_ns: int):
        self._clock = clock
        self._window_ns = window_ns
        self._started_ns = clock.now_ns()
        self._last_output_ns: Optional[int] = None

    def note_output(self) -> None:
        self._last_output_ns = self._clock.now_ns()

    def is_active(
        self,
        now_ns: int,
        *,
        cpu_usage: Optional[float] = None,
        cpu_threshold: Optional[float] = None,
    ) -> bool:
        # 启动后的第一个窗口内始终视为活跃，避免启动瞬间允许休眠
        if now_ns - self._started_ns < self._window_ns:
            return True
        if (
            self._last_output_ns is not None
            and now_ns - self._last_output_ns < self._window_ns
        ):
            return True
        if (
            cpu_threshold is not None
            and cpu_usage is not None
            and cpu_usage > cpu_threshold
        ):
            return True
        return False


def run_wrapped(config: CLIConfig, deps: WrapDeps) -> int:
    """包裹模式：按子进程活跃度按需切换休眠抑制，子进程退出即退出。"""
    tracker = ActivityTracker(deps.clock, int(config.window_secs * 1e9))
    child = deps.spawn(
        config.command,
        on_output=tracker.note_output,
        stdout=deps.stdout,
        stderr=deps.stderr,
    )
    deps.inhibitor.set_active(True)
    try:
        while child.poll() is None:
            # CPU 判定未启用时完全不采样
            cpu_usage = (
                deps.sample_child_cpu()
                if config.child_cpu_threshold is not None
                and deps.sample_child_cpu is not None
                else None
            )
            active = tracker.is_active(
                deps.clock.now_ns(),
                cpu_usage=cpu_usage,
                cpu_threshold=config.child_cpu_threshold,
            )
            deps.inhibitor.set_active(active)
            deps.clock.sleep(config.interval_secs)
        return int(child.wait())
    except KeyboardInterrupt:
        # 先中断子进程，等它自行退出；超时才强制结束，避免留下孤儿进程
        child.send_interrupt()
        try:
            child.wait(INTERRUPT_GRACE_SECS)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
        return 1
    finally:
        deps.inhibitor.set_active(False)


def run_wait(config: CLIConfig) -> int:
    """非包裹模式：持续抑制休眠，并按空闲判定在达到时长后退出。"""
    target_duration_ns = int(config.duration_secs * 1e9)
    cpu_threshold = config.cpu_threshold
    gpu_threshold = config.gpu_threshold
    vram_threshold = config.vram_threshold
    ignore_user_input = config.ignore_user_input
    interval_ns = int(config.interval_secs * 1e9)

    # 初始化等待
    threshold_msg = f"📊监控阈值: CPU ≤ {cpu_threshold}%, GPU ≤ {gpu_threshold}%"

    # 初始化等待所需的资源
    stack = ExitStack()
    checkers: list[BaseChecker] = []

    # 1. CPU 检查器
    _get_cpu = get_cpu_monitor_func(stack, cpu_threshold)
    if cpu_threshold < 100:
        checkers.append(ThresholdChecker("CPU", _get_cpu, cpu_threshold))

    # 2. GPU 检查器
    _get_gpu = get_gpu_monitor_func(stack, gpu_threshold)
    if gpu_threshold < 100:
        checkers.append(ThresholdChecker("GPU", _get_gpu, gpu_threshold))

    # 3. VRAM 检查器
    _get_vram = get_vram_monitor_func(stack, vram_threshold)
    if vram_threshold is not None:
        checkers.append(ThresholdChecker("VRAM", _get_vram, vram_threshold, unit="MB"))

    # 4. 用户输入检查器
    def _no_input():
        return None

    _get_input = get_since_last_input_ns
    if ignore_user_input:
        _get_input = _no_input
    elif get_since_last_input_ns() is None:
        _LOGGER.warning("未检测到用户输入检测支持，将忽略用户输入 (需 win32api)")
        _get_input = _no_input
    
    if not ignore_user_input and _get_input() is not None:
        checkers.append(InputChecker(_get_input))

    # 输出初始化信息
    threshold_msg = "📊监控阈值: " + ", ".join(c.threshold_text() for c in checkers)
    _LOGGER.info(threshold_msg)

    idle_start = None
    start_at = time.monotonic_ns()

    try:
        prevent_sleep()
        with tqdm(
            total=target_duration_ns / 1e9,
            bar_format="{n:.0f}/{total:.0f}s |{bar}|",
            disable=True if target_duration_ns == 0 else None,
        ) as progress, stack:
            last_tick = start_at

            for now in precise_ticker(interval_ns, immediate=False):
                # 更新所有检查器
                for checker in checkers:
                    checker.update(now, last_tick)

                # 检查是否全部空闲
                all_ok = all(checker.is_ok() for checker in checkers)

                if _LOGGER.isEnabledFor(logging.DEBUG):
                    status_line = " | ".join(checker.status_text() for checker in checkers)
                    _LOGGER.debug(status_line)

                if all_ok:
                    if idle_start is None:
                        if target_duration_ns == 0:
                            # 不进行下个循环直接终止
                            last_tick = now
                            break
                        idle_start = now
                        _LOGGER.debug("✅ 系统空闲，开始计时")
                        progress.reset()
                    else:
                        elapsed = now - idle_start
                        if elapsed >= target_duration_ns:
                            # 终止
                            last_tick = now
                            progress.leave = (
                                False  # 正常结束不残留进度条，异常保留中断时间
                            )
                            break
                        else:
                            progress.n = (
                                elapsed / 1e9
                            )  # 避免 update 使用浮点数加法进行计算
                            progress.update(0)  # 让进度条内部决定是否要刷新
                else:
                    if idle_start is not None:
                        if _LOGGER.isEnabledFor(logging.DEBUG):
                            reasons = [
                                checker.status_text()
                                for checker in checkers
                                if not checker.is_ok()
                            ]
                            _LOGGER.debug("❌ 重置计时器，原因：%s", "; ".join(reasons))
                        progress.reset()
                    idle_start = None
                last_tick = now
        if target_duration_ns == 0:
            _LOGGER.info("🎉系统空闲，退出等待")
        else:
            _LOGGER.info(f"🎉达到目标空闲时间 {target_duration_ns/1e9} 秒，退出等待")
        _LOGGER.info(f"⏱️ 总等待时间: {(last_tick - start_at)/1e9:.1f} 秒")
        return 0
    except KeyboardInterrupt:
        _LOGGER.info("用户中断等待")
        return 1
    except Exception as e:
        _LOGGER.exception(f"等待过程中发生错误: {str(e)}")
        return 1


class SystemClock:
    """生产环境使用的单调时钟。"""

    def now_ns(self) -> int:
        return time.monotonic_ns()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class SleepInhibitor:
    """按需切换休眠抑制，仅在状态变化时调用系统 API。"""

    def __init__(self, set_state: Optional[Callable[[bool], None]] = None):
        self._set_state = (
            set_state if set_state is not None else self._set_thread_execution_state
        )
        self._active = False

    @staticmethod
    def _set_thread_execution_state(active: bool) -> None:
        ES_CONTINUOUS = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED if active else ES_CONTINUOUS
        ctypes.windll.kernel32.SetThreadExecutionState(flags)

    def set_active(self, active: bool) -> None:
        if active == self._active:
            return
        self._set_state(active)
        self._active = active


class ProcessTreeCPUSampler:
    """用 PDH 统计子进程树的 CPU 占用百分比，不引入 psutil。"""

    def __init__(self, root_pid: Optional[int] = None):
        assert pythoncom is not None and win32pdh is not None
        self._root_pid = root_pid
        pythoncom.CoInitialize()
        self._com_initialized = True
        self._query = win32pdh.OpenQuery()
        self._cpu = win32pdh.AddCounter(
            self._query, r"\Process(*)\% Processor Time"
        )
        self._pid = win32pdh.AddCounter(self._query, r"\Process(*)\ID Process")
        self._ppid = win32pdh.AddCounter(
            self._query, r"\Process(*)\Creating Process ID"
        )
        win32pdh.CollectQueryData(self._query)

    def set_root_pid(self, root_pid: int) -> None:
        self._root_pid = root_pid

    @staticmethod
    def _to_int_map(items: dict) -> dict[str, int]:
        return {name: int(value) for name, value in items.items() if value is not None}

    def sample(self) -> Optional[float]:
        assert win32pdh is not None
        if self._root_pid is None:
            return None
        try:
            win32pdh.CollectQueryData(self._query)
            cpus = win32pdh.GetFormattedCounterArray(
                self._cpu, win32pdh.PDH_FMT_DOUBLE
            )
            pids = win32pdh.GetFormattedCounterArray(
                self._pid, win32pdh.PDH_FMT_LARGE
            )
            ppids = win32pdh.GetFormattedCounterArray(
                self._ppid, win32pdh.PDH_FMT_LARGE
            )
        except win32pdh.error:
            return None

        pid_by_instance = self._to_int_map(pids)
        ppid_by_instance = self._to_int_map(ppids)

        tree_pids = {self._root_pid}
        # 逐轮扩展进程树；层级有限，最多迭代 8 轮即可稳定
        for _ in range(8):
            added = False
            for name, pid in pid_by_instance.items():
                if pid in tree_pids:
                    continue
                if ppid_by_instance.get(name) in tree_pids:
                    tree_pids.add(pid)
                    added = True
            if not added:
                break

        total = 0.0
        for name, pid in pid_by_instance.items():
            if pid in tree_pids:
                value = cpus.get(name)
                if isinstance(value, (int, float)):
                    total += float(value)
        return total

    def cleanup(self) -> None:
        assert win32pdh is not None and pythoncom is not None
        if self._query:
            win32pdh.CloseQuery(self._query)
            self._query = None
        if self._com_initialized:
            pythoncom.CoUninitialize()
            self._com_initialized = False


@contextmanager
def default_wrap_deps(config: CLIConfig):
    """构建生产环境的包裹模式依赖，并在退出时释放系统资源。"""
    with ExitStack() as stack:
        sampler = None
        if config.child_cpu_threshold is not None:
            if all([win32pdh, pythoncom]):
                try:
                    sampler = ProcessTreeCPUSampler()
                    stack.callback(sampler.cleanup)
                except Exception as e:
                    _LOGGER.warning(f"子进程 CPU 监控初始化失败: {e}，将忽略该阈值")
                    sampler = None
            else:
                _LOGGER.warning("子进程 CPU 监控不可用: 需要 pywin32 库，将忽略该阈值")

        def spawn(command, *, on_output, stdout, stderr):
            handle = spawn_child(
                command, on_output=on_output, stdout=stdout, stderr=stderr
            )
            if sampler is not None:
                sampler.set_root_pid(handle.pid)
            return handle

        def sample_child_cpu() -> Optional[float]:
            return sampler.sample() if sampler is not None else None

        yield WrapDeps(
            clock=SystemClock(),
            inhibitor=SleepInhibitor(),
            spawn=spawn,
            sample_child_cpu=sample_child_cpu if sampler is not None else None,
            stdout=sys.stdout.buffer,
            stderr=sys.stderr.buffer,
        )


def main(
    argv: Optional[Sequence[str]] = None,
    *,
    wrap_deps: Optional[WrapDeps] = None,
):
    try:
        config = parse_cli(argv)
    except CLIArgumentError as e:
        _LOGGER.error("参数错误: %s", e)
        sys.exit(2)

    log_level = logging.DEBUG if config.verbose else logging.INFO
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    logging.basicConfig(level=log_level, format=log_format, stream=sys.stderr)

    if config.wrap:
        if wrap_deps is not None:
            sys.exit(run_wrapped(config, wrap_deps))
        with default_wrap_deps(config) as deps:
            sys.exit(run_wrapped(config, deps))
    else:
        sys.exit(run_wait(config))


if __name__ == "__main__":
    main()
