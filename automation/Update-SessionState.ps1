# 脚本用途：合集所有与会话状态同步相关的任务
# 1. PowerToys Awake 状态切换
# 2. Stretchly 启用/禁用

. "$PSScriptRoot\..\lib\Get-SessionStatus.ps1"
$isActiveRemote = Get-IsRemoteSession

# 把状态作为参数传递给各子脚本
& "$PSScriptRoot\Manage-PowerToysAwake.ps1" -IsRemote $isActiveRemote
& "$PSScriptRoot\Manage-Stretchly.ps1" -IsRemote $isActiveRemote
