"""
wait-idle.py - 等待系统空闲的监控脚本

该脚本持续监控系统资源使用情况，直到CPU和GPU占用率持续低于阈值达到指定时间后才退出。
适用于挂机渲染任务完成后的等待场景。

使用示例:
  # 基本用法
  python wait-idle.py && echo system-idle

  # 详细输出模式
  python wait-idle.py --verbose && echo system-idle

退出代码:
  0 - 成功达到目标空闲时间
  1 - 监控过程中出现错误
  2 - 参数错误
"""

import sys
import time
import logging
import argparse
import psutil
from typing import Iterator

_LOGGER = logging.getLogger(__name__)

try:
    import GPUtil
except ImportError:
    GPUtil = None


def get_cpu_usage():
    """获取当前CPU最高使用率（百分比）"""
    return psutil.cpu_percent()


def get_gpu_usage():
    """获取当前GPU最高使用率（百分比）"""
    if GPUtil is None:
        return None

    gpus = GPUtil.getGPUs()
    if not gpus:
        return None
    return max(gpu.load * 100 for gpu in gpus)


def precise_interval_iterator(interval: float) -> Iterator[float]:
    next_time = time.time() + interval
    while True:
        current_time = time.time()

        if current_time >= next_time:
            # 已经超时，立即 yield
            yield current_time
            next_time = current_time + interval
        else:
            # 计算剩余时间并 sleep
            sleep_time = next_time - current_time
            time.sleep(sleep_time)
            # sleep 结束后再 yield
            yield time.time()
            next_time += interval


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
    # 正常渲染任务都是占满的，阈值设太低可能光后台任务都视为非空闲了
    # XXX: 闲置时CPU占用率比资源管理器看到的要高，不知原因，测试满载时都是100%
    parser.add_argument("--cpu", type=float, default=50, help="CPU阈值")
    parser.add_argument("--gpu", type=float, default=50, help="GPU阈值")
    args = parser.parse_args()

    # 配置日志系统
    log_level = logging.DEBUG if args.verbose else logging.INFO
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    logging.basicConfig(level=log_level, format=log_format, stream=sys.stderr)

    # 校验参数
    target_duration_secs = args.duration_secs
    cpu_threshold = args.cpu
    gpu_threshold = args.gpu
    try:
        if target_duration_secs < 0:
            raise ValueError("等待时间不能为负数")

        if not (cpu_threshold >= 0 and cpu_threshold <= 100):
            raise ValueError("CPU 阈值应该为 0-100")

        if not (gpu_threshold >= 0 and gpu_threshold <= 100):
            raise ValueError("GPU 阈值应该为 0-100")
    except Exception as e:
        _LOGGER.error("参数错误: %s", e)
        sys.exit(2)

    # 初始化监控
    has_gpu = GPUtil is not None

    _LOGGER.info(f"⌛ 开始监控，需要持续空闲 {target_duration_secs} 秒")
    _LOGGER.info(f"监控阈值: CPU ≤ {cpu_threshold}%, GPU ≤ {gpu_threshold}%")
    if not has_gpu:
        _LOGGER.warning("未检测到GPU监控支持，将仅监控CPU使用率 (需安装 GPUtil)")

    idle_start = None
    start_time = time.time()
    try:
        psutil.cpu_percent()  # 记录 CPU 监控起始点
        for _ in precise_interval_iterator(1):
            cpu = get_cpu_usage()
            gpu = get_gpu_usage() if has_gpu else None

            # 检查资源使用情况
            cpu_ok = cpu <= cpu_threshold
            gpu_ok = (gpu is None) or (gpu <= gpu_threshold)

            _LOGGER.debug(
                f"CPU: {cpu:.1f}% | GPU: {gpu if gpu is not None else 'N/A'}%"
            )

            if cpu_ok and gpu_ok:
                if idle_start is None:
                    idle_start = time.time()
                    _LOGGER.info("✅ 系统空闲，开始计时")
                else:
                    elapsed = time.time() - idle_start
                    if elapsed >= target_duration_secs:
                        total_time = time.time() - start_time
                        _LOGGER.info(
                            f"🎉 达到目标空闲时间 {target_duration_secs} 秒，退出监控"
                        )
                        _LOGGER.info(f"⏱️ 总监控时间: {total_time:.1f} 秒")
                        sys.exit(0)
            else:
                if idle_start is not None:
                    _LOGGER.info("❌ 资源占用过高，重置计时器")
                idle_start = None

    except KeyboardInterrupt:
        _LOGGER.info("用户中断监控")
        sys.exit(1)
    except Exception as e:
        _LOGGER.exception(f"监控过程中发生错误: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
