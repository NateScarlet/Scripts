#Requires -Version 7.0
# video_compressor.ps1
# 视频压缩脚本，将一年前的视频文件转换为H.265格式

param(
    [Parameter(Mandatory = $true, HelpMessage = "输入目录路径")]
    [string]$InputDirectory,
    
    [Parameter(Mandatory = $true, HelpMessage = "输出目录路径")]
    [string]$OutputDirectory,
    
    [Parameter(HelpMessage = "是否递归处理子目录")]
    [switch]$Recursive,
    
    [Parameter(HelpMessage = "覆盖已存在的输出文件")]
    [switch]$Force 
)

$ErrorActionPreference = "Stop"

# 导入回收站函数
. "$PSScriptRoot/../../lib/Send-To-RecycleBin.ps1"


# 检查输入输出目录
if (-not (Test-Path -LiteralPath $InputDirectory -PathType Container)) {
    Write-Error "输入目录不存在: $InputDirectory"
    exit 1
}

if (-not (Test-Path -LiteralPath $OutputDirectory -PathType Container)) {
    try {
        New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
        Write-Host "已创建输出目录: $OutputDirectory"
    }
    catch {
        Write-Error "无法创建输出目录: $_"
        exit 1
    }
}

# 检查ffmpeg和ffprobe是否可用
try {
    $null = Get-Command ffmpeg -ErrorAction Stop
    $null = Get-Command ffprobe -ErrorAction Stop
}
catch {
    Write-Error "未找到ffmpeg/ffprobe，请确保已安装并添加到PATH"
    exit 1
}

# 定义视频文件扩展名
$videoExtensions = @('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg')

# 计算一年前的日期
$oneYearAgo = (Get-Date).AddYears(-1)

# 获取要处理的文件
$allFiles = Get-ChildItem -LiteralPath $InputDirectory -File -Recurse:$Recursive | Where-Object {
    $_.Extension -in $videoExtensions
}

# 筛选一年前的文件
$oldFiles = $allFiles | Where-Object {
    $_.LastWriteTime -lt $oneYearAgo
}

Write-Host "找到 $($allFiles.Count) 个视频文件，其中 $($oldFiles.Count) 个最后修改于一年前"

# 如果没有找到符合条件的文件，退出
if ($oldFiles.Count -eq 0) {
    Write-Host "没有找到需要处理的文件"
    exit 0
}

# 处理状态跟踪
$processedCount = 0
$skippedCount = 0
$failedCount = 0
$movedCount = 0
$convertedCount = 0
$startTime = Get-Date

# 函数：检查视频编码是否为H.265
function Test-H265Video {
    param(
        [string]$FilePath
    )
    
    try {
        # 使用ffprobe检测视频编码格式
        $ffprobeOutput = & ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of default=noprint_wrappers=1:nokey=1 "$FilePath"
        
        # 检查编码是否为H.265（包括hevc和libx265）
        if ($ffprobeOutput.Trim() -match '^(hevc|libx265)$') {
            return $true
        }
        return $false
    }
    catch {
        Write-Warning "无法检测文件编码: $FilePath ($_)"
        return $false
    }
}

foreach ($inputFile in $oldFiles) {
    $processedCount++
    
    # 计算相对于输入目录的路径（用于保持目录结构）
    $relativePath = [System.IO.Path]::GetRelativePath($InputDirectory, $inputFile.FullName)
    
    # 去除扩展名，添加.mkv扩展名
    $outputFileName = [System.IO.Path]::ChangeExtension($relativePath, ".mkv")
    $outputFile = Join-Path -Path $OutputDirectory -ChildPath $outputFileName
    $outputTempFile = "$outputFile.tmp"
    
    # 确保输出目录存在
    $outputDir = Split-Path -Path $outputFile -Parent
    if (-not (Test-Path -Path $outputDir)) {
        New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
    }
    
    Write-Host ""
    Write-Host "[$processedCount/$($oldFiles.Count)] 处理: $($inputFile.Name)"
    Write-Host "  输入: $($inputFile.FullName)"
    Write-Host "  输出: $outputFile"
    
    # 检查是否已存在最终输出文件
    if ((-not $Force) -and (Test-Path -Path $outputFile -PathType Leaf)) {
        Write-Host "  [跳过] 输出文件已存在"
        $skippedCount++
        continue
    }
    
    # 检查输入文件是否为H.265编码
    $isH265 = Test-H265Video -FilePath $inputFile.FullName
    
    # 检查是否存在临时文件（可能是上次中断留下的）
    if (Test-Path -Path $outputTempFile -PathType Leaf) {
        Write-Host "  [警告] 发现未完成的临时文件，将删除"
        Remove-Item -Path $outputTempFile -Force
    }
    
    # 转换视频
    # 如果已经是H.265编码
    if ($isH265) {
        Write-Host "  [信息] 文件已经是H.265编码，将不重新编码"
        $isMkv = $inputFile.Extension -eq '.mkv'

        # 如果已经是MKV格式，直接移动
        if ($isMkv) {
            Write-Host "  [信息] 文件已经是MKV格式，直接移动"
            try {
                Move-Item -LiteralPath $inputFile.FullName -Destination $outputFile
                Write-Host "  [成功] 文件已直接移动"
                $movedCount++
            }
            catch {
                Write-Host "  [错误] 文件移动失败: $_"
                $failedCount++
            }
        
            # 更新进度并继续下一个文件
            $elapsed = (Get-Date) - $startTime
            $estimatedTotal = if ($processedCount -gt 0) {
                $elapsed.TotalSeconds * $oldFiles.Count / $processedCount
            }
            else { 0 }
            $remaining = [timespan]::FromSeconds($estimatedTotal - $elapsed.TotalSeconds)
        
            Write-Host "  进度: $processedCount/$($oldFiles.Count) | 已用时: $($elapsed.ToString('hh\:mm\:ss')) | 预计剩余: $($remaining.ToString('hh\:mm\:ss'))"
            continue
        }
    
        # 如果不是MKV格式，重新封装为MKV而不重新编码
        Write-Host "  [信息] 文件将重新封装为MKV格式（不重新编码）"
        $ffmpegArgs = @(
            "-i", "`"$($inputFile.FullName)`"",
            "-map", "0",
            "-c", "copy",  # 复制所有流，不重新编码
            "-f", "matroska",
            "`"$outputTempFile`""
        )
    }
    # 如果不是H.265编码，需要重新编码
    else {
        Write-Host "  开始转换..."
        $ffmpegArgs = @(
            "-i", "`"$($inputFile.FullName)`"",
            "-map", "0",
            "-c:v", "libx265",
            "-crf", "22",
            "-preset", "slow",
            "-c:a", "copy",
            "-f", "matroska",
            "`"$outputTempFile`""
        )
    }

    # 执行转换或重新封装
    try {
        $process = Start-Process -PassThru -FilePath ffmpeg -ArgumentList $ffmpegArgs -NoNewWindow
        $process.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::BelowNormal
        $process.WaitForExit()

        if ($process.ExitCode -eq 0) {
            if (Test-Path -Path $outputTempFile -PathType Leaf) {
                Rename-Item -Path $outputTempFile -NewName $outputFile -Force
                Write-Host "  [成功] 处理完成"
                $convertedCount++
            
                # 移动原文件到回收站
                try {
                    Write-Host "  移动原文件到回收站..."
                    Send-To-RecycleBin $inputFile
                    Write-Host "  [完成] 原文件已移至回收站"
                }
                catch {
                    Write-Warning "  无法移动文件到回收站: $_"
                }
            }
            else {
                Write-Host "  [错误] 未找到处理后的文件"
                $failedCount++
            }
        }
        else {
            Write-Host "  [失败] ffmpeg错误，退出码: $($process.ExitCode)"
            $failedCount++
        
            # 清理临时文件
            if (Test-Path -LiteralPath $outputTempFile -PathType Leaf) {
                Remove-Item -LiteralPath $outputTempFile -Force
            }
        }
    }
    catch {
        Write-Host "  [错误] 处理过程中发生异常: $_"
        $failedCount++
    
        # 清理临时文件
        if (Test-Path -LiteralPath $outputTempFile -PathType Leaf) {
            Remove-Item -LiteralPath $outputTempFile -Force
        }
        # 中止进程
        if ($process -and (-not $process.HasExited)) {
            $process.Kill()
        }
    }
    
    # 显示进度
    $elapsed = (Get-Date) - $startTime
    $estimatedTotal = if ($processedCount -gt 0) {
        $elapsed.TotalSeconds * $oldFiles.Count / $processedCount
    }
    else { 0 }
    $remaining = [timespan]::FromSeconds($estimatedTotal - $elapsed.TotalSeconds)
    
    Write-Host "  进度: $processedCount/$($oldFiles.Count) | 已用时: $($elapsed.ToString('hh\:mm\:ss')) | 预计剩余: $($remaining.ToString('hh\:mm\:ss'))"
}

# 输出统计信息
$endTime = Get-Date
$totalTime = $endTime - $startTime

Write-Host ""
Write-Host "=" * 50
Write-Host "转换完成！"
Write-Host "总文件数: $($oldFiles.Count)"
Write-Host "已转换: $convertedCount"
Write-Host "已移动: $movedCount"
Write-Host "跳过: $skippedCount"
Write-Host "失败: $failedCount"
Write-Host "总用时: $($totalTime.ToString('hh\:mm\:ss'))"
Write-Host "=" * 50
