# Agent shell profile
# Runs before every bash-tool command (injected by the agent-profile plugin, since opencode launches pwsh with -NoProfile).
# Customize the agent's shell environment here: encoding, aliases, PSDefaultParameterValues, env vars, etc.

$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8

# 替代 no-powershell 插件：裸 powershell / powershell.exe 重定向到 pwsh。
# 别名仅在命令解析位置生效，不误伤字符串字面量；绝对路径调用不拦截（主动指定可能确实需要老版本）。
# 需 -Scope Global：profile 经 & 调用在子作用域，否则别名在脚本结束后消失。
Set-Alias powershell pwsh -Scope Global
Set-Alias powershell.exe pwsh -Scope Global

# 替代 git-no-sign 插件：禁止 git 提交签名
$env:GIT_CONFIG_COUNT = "1"
$env:GIT_CONFIG_KEY_0 = "commit.gpgsign"
$env:GIT_CONFIG_VALUE_0 = "false"
