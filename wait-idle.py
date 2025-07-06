"""
wait-idle.py - 等待系统空闲的等待脚本

该脚本持续等待系统资源使用情况，直到CPU和GPU占用率持续低于阈值达到指定时间后才退出。
适用于挂机渲染任务完成后的等待场景。

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

import sys
import time
import logging
import argparse
import psutil
from typing import Iterator, Optional

_LOGGER = logging.getLogger(__name__)

try:
    import GPUtil
except ImportError:
    GPUtil = None

try:
    import win32api
except ImportError:
    win32api = None


def get_since_last_input_ns() -> Optional[int]:
    if win32api:
        last_input = win32api.GetLastInputInfo()  # 用户最后一次输入时间（会溢出）
        current_uptime = win32api.GetTickCount()  # 当前系统运行时间（会溢出）
        idle_ms = (current_uptime - last_input) % 0x100000000  # 处理回绕
        return idle_ms * 1_000_000


def get_cpu_usage():
    """获取当前CPU总使用率（百分比）"""
    return psutil.cpu_percent()


def get_gpu_usage():
    """获取当前GPU最高使用率（百分比）"""
    if GPUtil is None:
        return None

    gpus = GPUtil.getGPUs()
    if not gpus:
        return None
    return max(gpu.load * 100 for gpu in gpus)


def precise_ticker(interval_ns: int) -> Iterator[int]:
    next_time = time.time_ns() + interval_ns
    while True:
        current_time = time.time_ns()

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
            yield time.time_ns()
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
    detect_user_input = not args.ignore_user_input
    interval_ns = int(args.interval_secs * 1e9)
    if detect_user_input:
        if get_since_last_input_ns() is None:
            _LOGGER.warning("未检测到用户输入检测支持，将忽略用户输入 (需 win32api)")
            detect_user_input = False
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

    _LOGGER.info(f"⌛ 开始等待，需要持续空闲 {target_duration_ns/1e9} 秒")
    _LOGGER.info(f"监控阈值: CPU ≤ {cpu_threshold}%, GPU ≤ {gpu_threshold}%")
    _get_gpu_usage = get_gpu_usage
    if get_gpu_usage() is None:
        _LOGGER.warning(
            "未检测到GPU监控支持，将忽略 GPU 阈值 (需安装 GPUtil 并且支持 nvidia-smi)"
        )
        _get_gpu_usage = lambda: None

    idle_start = None
    start_at = time.time_ns()
    try:
        psutil.cpu_percent()  # 记录 CPU 等待起始点
        last_tick = start_at
        for now in precise_ticker(interval_ns):
            cpu = get_cpu_usage()
            gpu = _get_gpu_usage()

            # 检查资源使用情况
            cpu_ok = cpu <= cpu_threshold
            gpu_ok = (gpu is None) or (gpu <= gpu_threshold)
            input_ok = True
            since_last_input_ns: int | None
            if detect_user_input:
                since_last_input_ns = get_since_last_input_ns()
                assert (
                    since_last_input_ns is not None
                ), "不支持时 detect_user_input 应该为 False"
                _LOGGER.debug("距离上次用户操作: %.3f 秒", since_last_input_ns / 1e9)
                # 只检查本周期是否有有输入，避免等双倍时间
                input_ok = since_last_input_ns >= (now - last_tick)

            gpu_status = f"{gpu:.1f}%" if gpu is not None else "N/A"
            _LOGGER.debug(f"CPU: {cpu:.1f}% | GPU: {gpu_status}")

            if cpu_ok and gpu_ok and input_ok:
                if idle_start is None:
                    if target_duration_ns == 0:
                        _LOGGER.info(f"🎉 系统空闲，退出等待")
                        sys.exit(0)
                    idle_start = now
                    _LOGGER.info("✅ 系统空闲，开始计时")
                else:
                    elapsed = now - idle_start
                    if elapsed >= target_duration_ns:
                        total_time_ns = now - start_at
                        _LOGGER.info(
                            f"🎉 达到目标空闲时间 {target_duration_ns/1e9} 秒，退出等待"
                        )
                        _LOGGER.info(f"⏱️ 总等待时间: {total_time_ns/1e9:.1f} 秒")
                        sys.exit(0)
            else:
                if idle_start is not None:
                    reason = ""
                    if not cpu_ok:
                        reason += f"CPU {cpu:.1f}%;"
                    if not gpu_ok:
                        reason += f"GPU {gpu_status};"
                    if not input_ok:
                        reason += (
                            f"用户于 {since_last_input_ns/1e9:.3f} 秒前进行了操作;"
                        )
                    _LOGGER.info("❌ 重置计时器，原因：%s", reason)
                idle_start = None
            last_tick = now

    except KeyboardInterrupt:
        _LOGGER.info("用户中断等待")
        sys.exit(1)
    except Exception as e:
        _LOGGER.exception(f"等待过程中发生错误: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
