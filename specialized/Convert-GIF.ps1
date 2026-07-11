#!/usr/bin/env pwsh
<#
.SYNOPSIS
将任意视频截取中央正方形区域，生成指定尺寸的 GIF 动画。

.DESCRIPTION
使用 ffmpeg 和 ffprobe，自动计算视频中央正方形裁剪区域，
生成优化调色板后再转换为 GIF，支持自定义尺寸、帧率和最大文件大小。
超过最大文件大小时自动裁剪视频尾部时长以满足限制。

.PARAMETER InputFile
输入视频文件路径（支持 MKV、MP4 等 ffmpeg 支持的所有格式）。

.PARAMETER OutputFile
输出 GIF 文件路径（可选，默认在输入文件同目录生成 `<文件名>_square.gif`）。

.PARAMETER Size
输出正方形 GIF 的边长（像素），默认 512。

.PARAMETER Fps
GIF 帧率（每秒帧数），默认 25。

.PARAMETER MaxSize
输出 GIF 最大文件大小（MB），默认 6。超过此大小时自动裁剪尾部时长。

.PARAMETER ExtractLoop
尝试从输入视频中检测最小无缝循环范围。使用帧感知哈希（32×32 缩略图 PSNR 比较）实现感官近似匹配。
找到后以循环点时长生成 GIF；若超过文件大小限制则报错，不会自动裁剪。
如果未找到合适的循环点也会报错。
#>

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$InputFile,
    
    [Parameter(Mandatory = $false)]
    [string]$OutputFile,
    
    [Parameter(Mandatory = $false)]
    [int]$Size = 512,
    
    [Parameter(Mandatory = $false)]
    [int]$Fps = 25,
    
    [Parameter(Mandatory = $false)]
    [int]$MaxSize = 6,
    
    [Parameter(Mandatory = $false)]
    [switch]$ExtractLoop
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

# #region 循环检测函数（帧感知哈希 PSNR 比较）
function Find-SeamlessLoop {
    param(
        [string]$InputFile,
        [string]$TempDir,
        [int]$AnalysisFps = 2,
        [double]$PsnrThreshold = 28.0,
        [double]$VideoDuration = 0,
        [double]$OutputFps = 25
    )

    Write-DebugVar "AnalysisFps" $AnalysisFps
    Write-DebugVar "PsnrThreshold" $PsnrThreshold
    Write-DebugVar "VideoDuration" $VideoDuration
    Write-DebugVar "OutputFps" $OutputFps

    # 提取参考帧（第 1 帧，缩小至 64×64 → 感官近似）
    $refFrame = Join-Path $TempDir "ref.png"
    & ffmpeg -i $InputFile -vf "select=eq(n\,0),scale=64:64" -vframes 1 -update 1 $refFrame -y
    if (-not (Test-Path $refFrame)) {
        Write-DebugVar "参考帧提取失败" ""
        return $null
    }

    # 各帧与参考帧 PSNR 比较。
    # 注意：参考帧是单帧，必须用 loop 铺满视频时长才能逐帧对比；
    # 两边 fps 统一后再传给 psnr 保证帧索引对齐。
    # 注意：Windows 路径中的 \ 和 : 在 filter graph 里是特殊字符，需要转义。
    $loopCount = if ($VideoDuration -gt 0) { [Math]::Ceiling($VideoDuration * $AnalysisFps) + 5 } else { 200 }
    Write-DebugVar "loopCount" $loopCount

    $psnrLog = Join-Path $TempDir "psnr.log"
    $psnrLogEscaped = $psnrLog -replace '\\', '\\\\' -replace ':', '\\:'
    & ffmpeg -i $InputFile -i $refFrame -filter_complex "[0:v]fps=${AnalysisFps},scale=64:64[vid];[1:v]loop=loop=${loopCount}:size=1,fps=${AnalysisFps}[ref];[vid][ref]psnr=stats_file=${psnrLogEscaped}" -an -f null - -y
    if (-not (Test-Path $psnrLog)) {
        Write-DebugVar "PSNR 分析失败" ""
        return $null
    }

    # 跳过前约 0.5 秒的帧避免与起始帧过近
    $skipFrames = [Math]::Max(5, [int]($AnalysisFps * 0.5))

    $bestPsnr = 0.0
    $bestFrame = -1

    foreach ($line in (Get-Content $psnrLog)) {
        # 新版 ffmpeg 在 n 与 psnr_avg 之间插入了 mse_* 字段
        if ($line -match 'n[:=]\s*(\d+).*?psnr_avg[:=]\s*([\d\.]+)') {
            $frame = [int]$Matches[1]
            $psnr = [double]$Matches[2]
            if ($frame -gt $skipFrames -and $psnr -gt $bestPsnr) {
                $bestPsnr = $psnr
                $bestFrame = $frame
            }
        }
    }

    if ($bestFrame -lt 0 -or $bestPsnr -lt $PsnrThreshold) {
        Write-DebugVar "最佳 PSNR" $bestPsnr
        Write-DebugVar "阈值" $PsnrThreshold
        return $null
    }

    # 匹配帧就是帧 0 的视觉等价物，应作为循环最后一帧包含进来
    $loopSeconds = $bestFrame / $AnalysisFps

    Write-DebugVar "最佳匹配帧" $bestFrame
    Write-DebugVar "最佳 PSNR" $bestPsnr
    Write-DebugVar "循环时长" $loopSeconds
    return $loopSeconds
}
# #endregion

# #region GIF 生成函数（调色板 + GIF 编码）
function Generate-PaletteAndGif {
    param([double]$Duration)

    Write-Host "  生成调色板（时长: $([Math]::Round($Duration, 2)) 秒）..."
    $paletteArgs = @(
        '-t', $Duration,
        '-i', $InputFile,
        '-vf', "crop=${cropSize}:${cropSize}:${cropX}:${cropY},scale=${Size}:${Size}:flags=lanczos,palettegen=stats_mode=diff",
        '-y', '-update', '1', $tempPalette
    )
    Write-DebugVar "paletteArgs" ($paletteArgs -join ' ')
    & ffmpeg $paletteArgs *>&1 | Write-Host
    if (-not (Test-Path $tempPalette)) {
        Write-Error "调色板生成失败"
        exit 1
    }

    Write-Host "  生成 GIF（时长: $([Math]::Round($Duration, 2)) 秒）..."
    $gifArgs = @(
        '-t', $Duration,
        '-i', $InputFile,
        '-i', $tempPalette,
        '-filter_complex', "[0:v]crop=${cropSize}:${cropSize}:${cropX}:${cropY},scale=${Size}:${Size}:flags=lanczos,fps=$Fps[v];[v][1:v]paletteuse",
        '-y', $OutputFile
    )
    Write-DebugVar "gifArgs" ($gifArgs -join ' ')
    & ffmpeg $gifArgs *>&1 | Write-Host

    if (-not (Test-Path $OutputFile)) {
        Write-Error "GIF 生成失败"
        exit 1
    }

    return (Get-Item $OutputFile).Length
}
# #endregion

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
Write-Host "最大文件大小: ${MaxSize} MB"
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

    # #region 获取视频时长
    Write-Host "步骤2/3: 获取视频时长..."
    $ffprobeDurationArgs = @(
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        $InputFile
    )
    Write-DebugVar "ffprobeDurationArgs" ($ffprobeDurationArgs -join ' ')
    $totalDurationRaw = & ffprobe $ffprobeDurationArgs *>&1
    $totalDurationStr = ($totalDurationRaw -split "`r`n" | Where-Object { $_ -match '^\d+\.?\d*$' } | Select-Object -First 1)
    if (-not $totalDurationStr) {
        Write-Error "无法获取视频时长"
        exit 1
    }
    $totalDuration = [double]$totalDurationStr
    Write-Host "  视频时长: $([Math]::Round($totalDuration, 2)) 秒"
    # #endregion

    # #region 步骤3/3：生成 GIF
    $maxSizeBytes = $MaxSize * 1MB

    if ($ExtractLoop) {
        Write-Host "步骤3/3: 检测无缝循环并生成 GIF（目标大小 ≤ ${MaxSize} MB）..."

        $tempLoopDir = Join-Path ([System.IO.Path]::GetTempPath()) "gif_loop_$(Get-Random)"
        New-Item -ItemType Directory -Force -Path $tempLoopDir | Out-Null

        try {
            Write-Host "  分析帧率: ${Fps} fps，缩略图: 64×64"
            $loopDuration = Find-SeamlessLoop -InputFile $InputFile -TempDir $tempLoopDir -AnalysisFps $Fps -PsnrThreshold 28.0 -VideoDuration $totalDuration -OutputFps $Fps

            if (-not $loopDuration) {
                Write-Error "未找到无缝循环点"
                exit 1
            }
            Write-Host "  找到循环点: $([Math]::Round($loopDuration, 2)) 秒"

            $fileSizeBytes = Generate-PaletteAndGif -Duration $loopDuration
            $fileSizeMB = $fileSizeBytes / 1MB

            if ($fileSizeBytes -gt $maxSizeBytes) {
                Write-Error "循环 GIF 大小 $([Math]::Round($fileSizeMB, 2)) MB 超过限制 ${MaxSize} MB（循环点已固定，无法缩短）"
                exit 1
            }

            Write-Host "========================================" -ForegroundColor Green
            Write-Host "✅ 成功生成循环 GIF！" -ForegroundColor Green
            Write-Host "  输出文件: $OutputFile"
            Write-Host "  文件大小: $([Math]::Round($fileSizeMB, 2)) MB / ${MaxSize} MB"
            Write-Host "  循环时长: $([Math]::Round($loopDuration, 2)) 秒"
            Write-Host "========================================" -ForegroundColor Green
        } finally {
            if (Test-Path $tempLoopDir) {
                Remove-Item $tempLoopDir -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
    } else {
        Write-Host "步骤3/3: 生成 GIF（大小限制 ${MaxSize} MB）..."
        $targetDuration = $totalDuration

        do {
            $fileSizeBytes = Generate-PaletteAndGif -Duration $targetDuration
            $fileSizeMB = $fileSizeBytes / 1MB

            if ($fileSizeBytes -gt $maxSizeBytes) {
                $scale = [Math]::Max($maxSizeBytes / $fileSizeBytes, 0.05)
                $newDuration = [Math]::Round($targetDuration * $scale, 2)
                if ([Math]::Abs($newDuration - $targetDuration) -lt 0.1) {
                    Write-Host "  文件大小 $([Math]::Round($fileSizeMB, 2)) MB 超过限制 ${MaxSize} MB，无法进一步缩短" -ForegroundColor Yellow
                    break
                }
                Write-Host "  文件大小 $([Math]::Round($fileSizeMB, 2)) MB 超过限制 ${MaxSize} MB，缩短到 ${newDuration} 秒重试" -ForegroundColor Yellow
                $targetDuration = $newDuration
            } else {
                break
            }
        } while ($true)

        if ($targetDuration -ge $totalDuration) {
            $effectiveDurationDisplay = "完整视频 ($([Math]::Round($totalDuration, 2)) 秒)"
        } else {
            $effectiveDurationDisplay = "$([Math]::Round($targetDuration, 2)) 秒"
        }

        Write-Host "========================================" -ForegroundColor Green
        Write-Host "✅ 成功生成 GIF！" -ForegroundColor Green
        Write-Host "  输出文件: $OutputFile"
        Write-Host "  文件大小: $([Math]::Round($fileSizeMB, 2)) MB / ${MaxSize} MB"
        Write-Host "  有效时长: $effectiveDurationDisplay"
        Write-Host "========================================" -ForegroundColor Green
    }
    # #endregion

} catch {
    Write-Error "处理过程中发生错误: $_"
    exit 1
} finally {
    if (Test-Path $tempPalette) { 
        Remove-Item $tempPalette -Force -ErrorAction SilentlyContinue 
        Write-Host "已清理临时调色板文件"
    }
}
