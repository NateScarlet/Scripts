# Agent shell profile
# Runs before every bash-tool command (injected by the agent-profile plugin, since opencode launches pwsh with -NoProfile).
# Customize the agent's shell environment here: encoding, aliases, PSDefaultParameterValues, env vars, etc.

$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8

# 替代 no-powershell 插件：裸 powershell / powershell.exe 重定向到 pwsh。
# 别名仅在命令解析位置生效，不误伤字符串字面量；绝对路径调用不拦截（主动指定可能确实需要老版本）。
# profile 经 . 点源加载在当前作用域，别名随命令会话保留。
Set-Alias powershell pwsh
Set-Alias powershell.exe pwsh

# 替代 no-npm 插件：npx 重定向到 pnpx（pnpm 提供的对应命令）
Set-Alias npx pnpx

# 替代 git-no-sign 插件：禁止 git 提交签名
$env:GIT_CONFIG_COUNT = "1"
$env:GIT_CONFIG_KEY_0 = "commit.gpgsign"
$env:GIT_CONFIG_VALUE_0 = "false"

# 临时产物统一放到项目根目录 .scratch 目录，避免污染系统临时目录
# 项目根目录由 agent-profile 插件注入（git 工作树），bash 在子目录运行时仍指向同一目录
if (-not $env:SCRATCH_DIR) {
  throw "[agent-profile] 缺少 SCRATCH_DIR 环境变量，请确认 agent-profile 插件已加载"
}
$env:TEMP = $env:SCRATCH_DIR
New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null
