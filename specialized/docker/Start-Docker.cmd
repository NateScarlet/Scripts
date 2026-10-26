
@echo off
rem 启动 Docker Desktop，并确保设置了自动重启的容器就位。
rem 用 -File 方式调用而非内联执行，保证 $PSScriptRoot 可用（脚本需加载 lib 中的通知模块）。
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-Docker.ps1" %*
if errorlevel 1 (
    echo.
    echo 执行失败，请查看上方输出。按任意键退出...
    pause >nul
)
