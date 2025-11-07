#!/bin/python3

import argparse
import socket
import logging

_LOGGER = logging.getLogger(__name__)

def resolve_ipv4(domain):
    try:
        addrinfo = socket.getaddrinfo(domain, None, socket.AF_INET)
        ips = {info[4][0] for info in addrinfo}
        sorted_ips = sorted(ips, key=lambda ip: socket.inet_aton(ip))
        return sorted_ips
    except socket.gaierror as e:
        print(f"Warning: Failed to resolve {domain}: {e}")
        return []

def process_file(file_path):
    with open(file_path, 'r') as f:
        lines = f.readlines()

    processed_lines = []
    current_domains = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 收集#include指令
        if stripped.startswith('#include'):
            parts = stripped.split()
            if len(parts) >= 2:
                current_domains.append(parts[1])
            processed_lines.append(line)
            i += 1
            continue

        # 处理sourceRange块
        if current_domains and 'sourceRange = [' in stripped:
            j = i
            array_lines = []
            while j < len(lines):
                current_line = lines[j]
                array_lines.append(current_line)
                if current_line.strip() == ']':
                    break
                j += 1
            else:  # 未找到闭合]
                processed_lines.extend(lines[i:j+1])
                i = j + 1
                current_domains = []
                continue

            # 分离手动条目和生成条目
            non_generated = []
            for ln in array_lines[1:-1]:
                if '# resolved from' not in ln:
                    non_generated.append(ln)

            # 解析所有域名IP并合并
            all_ips = []
            for domain in current_domains:
                ips = resolve_ipv4(domain)
                all_ips.extend([(ip, domain) for ip in ips])

            # 去重并排序（先按IP数值排序，再按域名排序）
            unique_ips = {}
            for ip, domain in all_ips:
                if ip not in unique_ips:
                    unique_ips[ip] = domain
                # 保留最后出现的域名注释
                else:
                    unique_ips[ip] = domain

            sorted_entries = sorted(
                unique_ips.items(),
                key=lambda x: (socket.inet_aton(x[0]), x[1])
            )

            # 生成新条目
            new_entries = [
                f'    "{ip}", # resolved from {domain}\n'
                for ip, domain in sorted_entries
            ]

            # 构建新数组
            new_array = [array_lines[0]]  # [
            new_array.extend(non_generated)  # 保留手动条目
            new_array.extend(new_entries)    # 新增解析条目
            new_array.append(array_lines[-1]) # ]

            processed_lines.extend(new_array)
            current_domains = []
            i = j + 1
        else:
            # 遇到非相关行时清空域名缓存
            if stripped:  # 忽略空行
                current_domains = []
            processed_lines.append(line)
            i += 1

    # 仅当内容变化时写入文件
    if processed_lines != lines:
        with open(file_path, 'w') as f:
            f.writelines(processed_lines)
        print(file_path)
        _LOGGER.info(f"Updated {file_path}")
    else:
        _LOGGER.debug(f"No changes needed for {file_path}")

def main():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument('file_path', nargs='*', help='Path to the TOML file')
    args = parser.parse_args()
    for i in args.file_path:
        process_file(i)

if __name__ == '__main__':
    main()
