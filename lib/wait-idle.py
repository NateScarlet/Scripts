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

退出代码:
  0 - 成功达到目标空闲时间
  1 - 等待过程中出现错误
  2 - 参数错误
"""

# pyright: standard

import sys
import time
import logging
import argparse
from typing import Iterator, Optional, Callable
from tqdm import tqdm
import ctypes
from contextlib import ExitStack

_LOGGER = logging.getLogger(__name__)

# Windows API 相关导入
try:
    import win32api
    import win32pdh
    import pythoncom
except ImportError:
    win32api = None
    win32pdh = None
    pythoncom = None


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

        data = win32pdh.GetFormattedCounterValue(
            self._counter_handle, win32pdh.PDH_FMT_DOUBLE
        )
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
            except:
                pass
            self._counter_handle = None

        if self._query_handle:
            try:
                assert win32pdh
                win32pdh.CloseQuery(self._query_handle)
            except:
                pass
            self._query_handle = None

        if self._com_initialized:
            try:
                assert pythoncom
                pythoncom.CoUninitialize()
            except:
                pass
            self._com_initialized = False


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

            if data and any(data.values()):
                self._query_handle = query_handle
                self._counter_handle = counter_handle
                return True

            win32pdh.CloseQuery(query_handle)
            return False

        except Exception as e:
            if query_handle:
                try:
                    win32pdh.CloseQuery(query_handle)
                except:
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

        items: dict = win32pdh.GetFormattedCounterArray(
            self._counter_handle, win32pdh.PDH_FMT_DOUBLE
        )
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

        items: dict = win32pdh.GetFormattedCounterArray(
            self._counter_handle, win32pdh.PDH_FMT_LARGE
        )
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
            except:
                pass
            self._query_handle = None
            self._counter_handle = None

        if self._com_initialized:
            try:
                assert pythoncom
                pythoncom.CoUninitialize()
            except:
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
    返回获取 CPU 使用率的函数
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


def main():
    # 设置参数解析
    parser = argparse.ArgumentParser(
        description="等待系统空闲持续指定时间",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "duration_secs",
        nargs="?",
        type=float,
        default=600,
        help="需要持续空闲的时间（秒）",
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
    parser.add_argument("--interval-secs", type=float, default=1.0, help="检测间隔(秒)")
    args = parser.parse_args()

    # 配置日志系统
    log_level = logging.DEBUG if args.verbose else logging.INFO
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    logging.basicConfig(level=log_level, format=log_format, stream=sys.stderr)

    # 校验参数
    target_duration_ns = int(args.duration_secs * 1e9)
    cpu_threshold = args.cpu
    gpu_threshold = args.gpu
    ignore_user_input = args.ignore_user_input
    interval_ns = int(args.interval_secs * 1e9)
    try:
        if target_duration_ns < 0:
            raise ValueError("等待时间不能为负数")

        if not (0 <= cpu_threshold <= 100):
            raise ValueError("CPU 阈值应该为 0-100")

        if not (0 <= gpu_threshold <= 100):
            raise ValueError("GPU 阈值应该为 0-100")

        if not (interval_ns > 0):
            raise ValueError("检测间隔应该大于 0")
    except Exception as e:
        _LOGGER.error("参数错误: %s", e)
        sys.exit(2)

    # 初始化等待
    _LOGGER.info(f"📊监控阈值: CPU ≤ {cpu_threshold}%, GPU ≤ {gpu_threshold}%")

    # 获取 CPU 和 GPU 监控上下文和函数
    stack = ExitStack()
    _get_cpu_usage = get_cpu_monitor_func(stack, cpu_threshold)
    _get_gpu_usage = get_gpu_monitor_func(stack, gpu_threshold)

    _get_since_last_input_ns = get_since_last_input_ns
    if ignore_user_input:
        _get_since_last_input_ns = lambda: None
    elif get_since_last_input_ns() is None:
        _LOGGER.warning("未检测到用户输入检测支持，将忽略用户输入 (需 win32api)")
        _get_since_last_input_ns = lambda: None

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
                cpu = _get_cpu_usage()
                gpu = _get_gpu_usage()
                since_last_input_ns = _get_since_last_input_ns()

                # 检查资源使用情况
                cpu_ok = (cpu is None) or (cpu <= cpu_threshold)
                gpu_ok = (gpu is None) or (gpu <= gpu_threshold)
                input_ok = (since_last_input_ns is None) or (
                    since_last_input_ns >= (now - last_tick)
                )

                cpu_status = None
                gpu_status = None
                input_status = None
                if _LOGGER.isEnabledFor(logging.DEBUG):
                    cpu_status = f"{cpu:.1f}%" if cpu is not None else "N/A"
                    gpu_status = f"{gpu:.1f}%" if gpu is not None else "N/A"
                    input_status = (
                        f"{since_last_input_ns/1e9:.3f}秒"
                        if since_last_input_ns is not None
                        else "N/A"
                    )
                    _LOGGER.debug(
                        f"CPU: {cpu_status} | GPU: {gpu_status} | 距用户上次操作: {input_status}"
                    )

                if cpu_ok and gpu_ok and input_ok:
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
                            reason = ""
                            if not cpu_ok:
                                reason += f"CPU {cpu_status}%;"
                            if not gpu_ok:
                                reason += f"GPU {gpu_status};"
                            if not input_ok:
                                reason += f"用户于 {input_status} 前进行了操作;"
                            _LOGGER.debug("❌ 重置计时器，原因：%s", reason)
                        progress.reset()
                    idle_start = None
                last_tick = now
        if target_duration_ns == 0:
            _LOGGER.info(f"🎉系统空闲，退出等待")
        else:
            _LOGGER.info(f"🎉达到目标空闲时间 {target_duration_ns/1e9} 秒，退出等待")
        _LOGGER.info(f"⏱️ 总等待时间: {(last_tick - start_at)/1e9:.1f} 秒")
        sys.exit(0)
    except KeyboardInterrupt:
        _LOGGER.info("用户中断等待")
        sys.exit(1)
    except Exception as e:
        _LOGGER.exception(f"等待过程中发生错误: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
