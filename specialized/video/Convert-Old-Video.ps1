#Requires -Version 7.0
# 视频压缩脚本，处理一年前的视频文件

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

# 函数：获取视频信息
function Get-VideoInfo {
    param(
        [string]$FilePath
    )
    
    try {
        # 获取视频的基本信息
        $ffprobeOutput = & ffprobe -v error -select_streams v:0 -show_entries stream=codec_name, width, height, bit_rate -show_entries format=bit_rate, duration -of json "$FilePath" | ConvertFrom-Json
        
        $videoStream = $ffprobeOutput.streams[0]
        $format = $ffprobeOutput.format
        
        $info = @{
            Codec    = $videoStream.codec_name
            Width    = [int]$videoStream.width
            Height   = [int]$videoStream.height
            # 优先使用流级别的码率，如果没有则使用容器级别的码率
            Bitrate  = if ($videoStream.bit_rate) { [int]$videoStream.bit_rate } else { [int]$format.bit_rate }
            Duration = [double]$format.duration
        }
        
        return $info
    }
    catch {
        Write-Warning "无法获取视频信息: $FilePath ($_)"
        return $null
    }
}

# 函数：获取分辨率阈值
function Get-ResolutionThreshold {
    param(
        [int]$Width,
        [int]$Height
    )
    
    $pixelCount = $Width * $Height
    
    if ($pixelCount -ge 8294400) {
        # 4K: 3840x2160 = 8,294,400
        return 8000
    }
    elseif ($pixelCount -ge 3686400) {
        # 1440p: 2560x1440 = 3,686,400
        return 4000
    }
    elseif ($pixelCount -ge 2073600) {
        # 1080p: 1920x1080 = 2,073,600
        return 2000
    }
    elseif ($pixelCount -ge 921600) {
        # 720p: 1280x720 = 921,600
        return 1000
    }
    elseif ($pixelCount -ge 409920) {
        # 480p: 854x480 = 409,920
        return 500
    }
    else {
        return 300
    }
}

# 函数：测试压缩比（比较比特率）
function Test-CompressionRatio {
    param(
        [hashtable]$OriginalVideoInfo,
        [string]$InputFilePath,
        [string]$TempFilePath
    )
    
    if (-not $OriginalVideoInfo) {
        Write-Warning "没有原始视频信息"
        return -1
    }
    
    $testDuration = 10
    $originalBitrate = $OriginalVideoInfo.Bitrate
    $originalDuration = $OriginalVideoInfo.Duration
    
    if (-not $originalBitrate -or $originalBitrate -le 0) {
        Write-Warning "原始视频比特率无效: $InputFilePath"
        return -1
    }
    
    if (-not $originalDuration -or $originalDuration -le 0) {
        Write-Warning "原始视频时长无效: $InputFilePath"
        return -1
    }
    
    $compressionRatio = -1
    $actualTestDuration = [Math]::Min($testDuration, $originalDuration)
    
    # 创建测试编码，使用AV1编码器
    $testArgs = @(
        "-i", "`"$InputFilePath`"",
        "-t", $actualTestDuration.ToString(),
        "-c:v", "libsvtav1",
        "-crf", "30",
        "-preset", "8",  # AV1 preset: 0-13, 0=最慢/最好质量，13=最快/最差质量
        "-an",  # 不编码音频
        "-f", "matroska",
        "`"$TempFilePath`""
    )
    
    try {
        $process = Start-Process -PassThru -FilePath ffmpeg -ArgumentList $testArgs -NoNewWindow
        $process.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::BelowNormal
        $process.WaitForExit()
        
        if ($process.ExitCode -ne 0) {
            Write-Warning "测试编码失败: $InputFilePath"
            return -1
        }
        
        if (-not (Test-Path -Path $TempFilePath -PathType Leaf)) {
            Write-Warning "未生成测试文件: $TempFilePath"
            return -1
        }
        
        # 获取测试文件的比特率
        $testInfo = & ffprobe -v error -select_streams v:0 -show_entries stream=bit_rate -of json "$TempFilePath" | ConvertFrom-Json
        if (-not $testInfo -or -not $testInfo.streams[0]) {
            Write-Warning "无法解析测试文件信息: $TempFilePath"
            return -1
        }
        
        $testBitrate = [double]$testInfo.streams[0].bit_rate
        if (-not $testBitrate -or $testBitrate -le 0) {
            Write-Warning "无法获取测试文件的视频比特率: $TempFilePath"
            return -1
        }
        
        # 计算比特率压缩比
        $compressionRatio = $testBitrate / $originalBitrate
        
        Write-Host "  [测试编码] 原始比特率: $([math]::Round($originalBitrate/1000, 2)) kbps, 测试比特率: $([math]::Round($testBitrate/1000, 2)) kbps"
        
        return $compressionRatio
    }
    catch {
        Write-Warning "测试压缩比失败: $InputFilePath ($_)"
        return -1
    }
    finally {
        # 中止进程
        if ($process -and (-not $process.HasExited)) {
            $process.Kill()
        }
        # 清理测试文件
        if (Test-Path -Path $TempFilePath -PathType Leaf) {
            Remove-Item -Path $TempFilePath -Force -ErrorAction SilentlyContinue
        }
    }
}


# 函数：评估是否值得转码
function Test-WorthTranscoding {
    param(
        [string]$FilePath
    )
    
    $videoInfo = Get-VideoInfo -FilePath $FilePath
    
    if (-not $videoInfo) {
        return $true  # 如果无法获取视频信息，则进行转码
    }
    
    # 步骤1: 快速筛选 - 基于分辨率和码率
    $threshold = Get-ResolutionThreshold -Width $videoInfo.Width -Height $videoInfo.Height
    
    # 码率单位转换: bps 到 kbps
    $bitrateKbps = [math]::Round($videoInfo.Bitrate / 1000)
    
    Write-Host "  [评估] 分辨率: $($videoInfo.Width)x$($videoInfo.Height), 编码: $($videoInfo.Codec), 码率: $bitrateKbps kbps, 阈值: $threshold kbps"
    
    if ($bitrateKbps -lt $threshold) {
        Write-Host "  [评估结果] 码率低于阈值，直接复制"
        return $false
    }
    
    # 步骤2: 精确验证 - 测试编码
    Write-Host "  [评估] 进行10秒测试编码..."
    $testFile = "$FilePath.test.mkv"
    $compressionRatio = Test-CompressionRatio -OriginalVideoInfo $videoInfo -InputFilePath $FilePath -TempFilePath $testFile

    Write-Host "  [评估] 压缩比: $([math]::Round($compressionRatio, 2))"

    if ($compressionRatio -gt 0.8) {
        Write-Host "  [评估结果] 压缩效果不佳，直接复制"
        return $false
    }
    
    # 测试失败不代表无法转码，所以值得转码
    Write-Host "  [评估结果] 值得转码"
    return $true
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
    
    # 检查是否存在临时文件（可能是上次中断留下的）
    if (Test-Path -Path $outputTempFile -PathType Leaf) {
        Write-Host "  [警告] 发现未完成的临时文件，将删除"
        Remove-Item -Path $outputTempFile -Force
    }
    
    # 转换视频

    Write-Host "  [信息] 评估是否值得转码..."
    $worthTranscoding = Test-WorthTranscoding -FilePath $inputFile.FullName
        
    if ($worthTranscoding) {
        Write-Host "  [信息] 文件值得转码，开始转换为AV1..."
        # 使用AV1编码器，保留所有音轨和字幕
        $ffmpegArgs = @(
            "-i", "`"$($inputFile.FullName)`"",
            "-map", "0",  # 映射所有流
            "-c:v", "libsvtav1",  # AV1编码器
            "-crf", "30",  # AV1的CRF范围通常为0-63，30是良好的平衡点
            "-preset", "6",  # AV1 preset: 0-13, 6是速度与质量的良好平衡
            "-c:a", "copy",  # 复制所有音频流
            "-c:s", "copy",  # 复制所有字幕流
            "-c:d", "copy",  # 复制所有数据流
            "-f", "matroska",
            "`"$outputTempFile`""
        )
    }
    elseif ($inputFile.Extension -eq '.mkv') {
        Write-Host "  [信息] 文件不值得转码，已经是MKV格式，直接移动"
        try {
            Move-Item -LiteralPath $inputFile.FullName -Destination $outputFile -Force:$Force
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
    else {
        Write-Host "  [信息] 文件不值得转码，重新封装为MKV（不重新编码）"
        $ffmpegArgs = @(
            "-i", "`"$($inputFile.FullName)`"",
            "-map", "0",  # 映射所有流
            "-c", "copy",  # 复制所有流，不重新编码
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
    
        # 中止进程
        if ($process -and (-not $process.HasExited)) {
            $process.Kill()
        }
        # 清理临时文件
        if (Test-Path -LiteralPath $outputTempFile -PathType Leaf) {
            Remove-Item -LiteralPath $outputTempFile -Force
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
