#!/bin/bash
# 创建唯一临时文件
STDOUT="$(mktemp)"
STDERR="$(mktemp)"

# 执行命令并分别捕获 stdout/stderr
"$@" > "$STDOUT" 2> "$STDERR"
EXIT_CODE=$?

# 仅在失败时输出
if [ $EXIT_CODE -ne 0 ]; then
    cat "$STDOUT"
    cat "$STDERR" >&2
fi

# 清理临时文件
rm -f "$STDOUT" "$STDERR"
exit $EXIT_CODE
