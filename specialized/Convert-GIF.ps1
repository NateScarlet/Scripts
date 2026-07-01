#!/usr/bin/env pwsh
<#
.SYNOPSIS
将任意视频截取中央正方形区域，生成指定尺寸的 GIF 动画。

.DESCRIPTION
使用 ffmpeg 和 ffprobe，自动计算视频中央正方形裁剪区域，
生成优化调色板后再转换为 GIF，支持自定义尺寸和帧率。

.PARAMETER InputFile
输入视频文件路径（支持 MKV、MP4 等 ffmpeg 支持的所有格式）。

.PARAMETER OutputFile
输出 GIF 文件路径（可选，默认在输入文件同目录生成 `<文件名>_square.gif`）。

.PARAMETER Size
输出正方形 GIF 的边长（像素），默认 512。

.PARAMETER Fps
GIF 帧率（每秒帧数），默认 15。
#>

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$InputFile,
    
    [Parameter(Mandatory = $false)]
    [string]$OutputFile,
    
    [Parameter(Mandatory = $false)]
    [int]$Size = 512,
    
    [Parameter(Mandatory = $false)]
    [int]$Fps = 15
)

# -------- 调试函数：打印变量 --------
function Write-DebugVar {
    param([string]$Name, $Value)
    Write-Host "[DEBUG] $Name = '$Value'" -ForegroundColor Cyan
}

# -------- 检查 ffmpeg --------
function Test-Ffmpeg {
    try { $null = Get-Command ffmpeg -ErrorAction Stop; return $true }
    catch { return $false }
}
if (-not (Test-Ffmpeg)) {
    Write-Error "未找到 ffmpeg，请安装并添加到 PATH"
    exit 1
}

# -------- 输入文件处理 --------
$InputFile = $InputFile.Trim()
if (-not (Test-Path $InputFile)) {
    Write-Error "输入文件不存在: $InputFile"
    exit 1
}
$InputFile = Resolve-Path $InputFile
Write-DebugVar "InputFile" $InputFile

# -------- 生成输出文件路径 --------
if (-not $OutputFile) {
    $dir = Split-Path $InputFile -Parent
    $base = [System.IO.Path]::GetFileNameWithoutExtension($InputFile)
    $OutputFile = Join-Path $dir "${base}_square.gif"
} else {
    $OutputFile = $OutputFile.Trim()
    # 如果是相对路径，转为绝对路径
    if (-not [System.IO.Path]::IsPathRooted($OutputFile)) {
        $OutputFile = Join-Path (Get-Location) $OutputFile
    }
}
# 确保扩展名为 .gif
if ([System.IO.Path]::GetExtension($OutputFile) -ne '.gif') {
    $OutputFile = [System.IO.Path]::ChangeExtension($OutputFile, '.gif')
}
# 获取完整路径，并去除尾部空白/换行
$OutputFile = [System.IO.Path]::GetFullPath($OutputFile).Trim()
Write-DebugVar "OutputFile" $OutputFile

# -------- 显示摘要信息 --------
Write-Host "========================================"
Write-Host "MKV to Square GIF Converter"
Write-Host "========================================"
Write-Host "输入文件: $InputFile"
Write-Host "输出文件: $OutputFile"
Write-Host "目标尺寸: ${Size}x${Size} 像素"
Write-Host "帧率: $Fps fps"
Write-Host "========================================"

# -------- 临时调色板文件 --------
$tempPalette = [System.IO.Path]::GetTempFileName()
$tempPalette = [System.IO.Path]::ChangeExtension($tempPalette, '.png')
# 确保不冲突（如果已存在则加随机数）
while (Test-Path $tempPalette) {
    $tempPalette = [System.IO.Path]::GetTempFileName() -replace '\.tmp\.', '.png'
}
$tempPalette = [System.IO.Path]::GetFullPath($tempPalette).Trim()
Write-DebugVar "tempPalette" $tempPalette

try {
    # -------- 步骤1：获取视频尺寸 --------
    Write-Host "步骤1/3: 分析视频尺寸..."
    $ffprobeArgs = @(
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        $InputFile
    )
    Write-DebugVar "ffprobeArgs" ($ffprobeArgs -join ' ')
    $dimensions = & ffprobe $ffprobeArgs *>&1
    $dimLines = $dimensions -split "`r`n" | Where-Object { $_ -match '^\d+$' }
    if ($dimLines.Count -lt 2) {
        Write-Error "无法获取视频尺寸，ffprobe 输出：$dimensions"
        exit 1
    }
    $width = [int]$dimLines[0]
    $height = [int]$dimLines[1]
    Write-Host "  原始视频尺寸: ${width}x${height}"

    # 计算裁剪区域
    $cropSize = [Math]::Min($width, $height)
    $cropX = [Math]::Floor(($width - $cropSize) / 2)
    $cropY = [Math]::Floor(($height - $cropSize) / 2)
    Write-Host "  裁剪区域: 从 ($cropX, $cropY) 裁剪 ${cropSize}x${cropSize}"

    # -------- 步骤2：生成调色板 --------
    Write-Host "步骤2/3: 生成调色板..."
    $paletteArgs = @(
        '-i', $InputFile,
        '-vf', "crop=${cropSize}:${cropSize}:${cropX}:${cropY},scale=${Size}:${Size}:flags=lanczos,palettegen=stats_mode=diff",
        '-y', $tempPalette
    )
    Write-DebugVar "paletteArgs" ($paletteArgs -join ' ')
    & ffmpeg $paletteArgs *>&1 | Write-Host
    if (-not (Test-Path $tempPalette)) {
        Write-Error "调色板生成失败"
        exit 1
    }

    # -------- 步骤3：生成 GIF --------
    Write-Host "步骤3/3: 生成GIF动画..."
    $gifArgs = @(
        '-i', $InputFile,
        '-i', $tempPalette,
        '-filter_complex', "[0:v]crop=${cropSize}:${cropSize}:${cropX}:${cropY},scale=${Size}:${Size}:flags=lanczos,fps=$Fps[v];[v][1:v]paletteuse",
        '-y', $OutputFile
    )
    Write-DebugVar "gifArgs" ($gifArgs -join ' ')
    Write-Host "即将执行 ffmpeg ..." -ForegroundColor Yellow
    & ffmpeg $gifArgs *>&1 | Write-Host

    # -------- 检查结果 --------
    if (Test-Path $OutputFile) {
        $fileSize = (Get-Item $OutputFile).Length / 1MB
        Write-Host "========================================" -ForegroundColor Green
        Write-Host "✅ 成功生成 GIF！" -ForegroundColor Green
        Write-Host "  输出文件: $OutputFile"
        Write-Host "  文件大小: $([Math]::Round($fileSize, 2)) MB"
        Write-Host "========================================" -ForegroundColor Green
    } else {
        Write-Error "GIF 生成失败，输出文件不存在"
        exit 1
    }

} catch {
    Write-Error "处理过程中发生错误: $_"
    exit 1
} finally {
    if (Test-Path $tempPalette) { 
        Remove-Item $tempPalette -Force -ErrorAction SilentlyContinue 
        Write-Host "已清理临时调色板文件"
    }
}
