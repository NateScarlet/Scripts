#Requires -Version 7.0
# 视频压缩脚本

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

#region 函数

# 导入回收站函数
. "$PSScriptRoot/../lib/Send-To-RecycleBin.ps1"


function Get-VideoInfo {
    param(
        [string]$FilePath
    )
    
    try {
        # 获取视频的基本信息
        $ffprobeOutput = & ffprobe -v error -select_streams v:0 -show_entries "stream=codec_name,width,height,bit_rate" -show_entries "format=bit_rate,duration" -of json "$FilePath" | ConvertFrom-Json
        
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

function Start-TwoPassEncoding {
    param(
        [string]$InputFile,
        [string]$OutputFile,
        [array]$Pass1OutputArgs,
        [array]$Pass2OutputArgs
    )
    
    $passLogFile = "$OutputFile.passlog"
    $outputTempFile = "$OutputFile.tmp"
    
    # 清理之前的临时文件
    if (Test-Path $outputTempFile) {
        Remove-Item -LiteralPath $outputTempFile -Force
    }
    
    try {
        # 第一遍：分析视频，不输出视频流
        Write-Host "  [第一遍] 开始分析视频..."
        $firstPassArgs = @(
            "-i", "`"$InputFile`""
            @($Pass1OutputArgs)
            "-pass", "1"
            "-passlogfile", "`"$passLogFile`""
            "-f", "null"
            "NUL"
        )
        
        $firstPassProcess = Start-Process -PassThru -FilePath ffmpeg -ArgumentList $firstPassArgs -NoNewWindow
        $firstPassProcess.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::BelowNormal
        $firstPassProcess.WaitForExit()
        
        if ($firstPassProcess.ExitCode -ne 0) {
            Write-Host "  [第一遍] 分析失败，退出码: $($firstPassProcess.ExitCode)"
            return $false
        }
        
        # 等待确保日志文件写入完成
        Start-Sleep -Milliseconds 100
        
        if (-not (Test-Path -Path "$passLogFile-*.log" -PathType Leaf)) {
            Write-Host "  [错误] 未生成passlog文件: $passLogFile"
            return $false
        }
        
        # 第二遍：使用第一遍的统计信息进行编码
        Write-Host "  [第二遍] 开始编码视频..."
        $secondPassArgs = @(
            "-hide_banner"
            "-i", "`"$InputFile`""
            @($Pass2OutputArgs)
            "-pass", "2"
            "-passlogfile", "`"$passLogFile`""
            "`"$outputTempFile`""
        )

        $secondPassProcess = Start-Process -PassThru -FilePath ffmpeg -ArgumentList $secondPassArgs -NoNewWindow
        $secondPassProcess.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::BelowNormal
        $secondPassProcess.WaitForExit()
        
        if ($secondPassProcess.ExitCode -ne 0) {
            Write-Host "  [第二遍] 编码失败，退出码: $($secondPassProcess.ExitCode)"
            return $false
        }
        
        if (Test-Path -Path $outputTempFile -PathType Leaf) {
            Move-Item -LiteralPath $outputTempFile -Destination $OutputFile -Force
            return $true
        }
        else {
            Write-Host "  [错误] 未生成输出文件"
            return $false
        }
        
    }
    catch {
        Write-Host "  [错误] 两遍编码过程中发生异常: $_"
        return $false
    }
    finally {
        # 清理临时文件
        if (Test-Path -Path $outputTempFile -PathType Leaf) {
            Remove-Item -LiteralPath $outputTempFile -Force
        }
        if (Test-Path -Path "$passLogFile-*.log" -PathType Leaf) {
            Remove-Item -Path "$passLogFile-*.log" -Force
        }
    }
}

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
    
    # 构建测试编码的两遍参数
    $testPass1Args = @(
        @($baseOutputArgs)
        "-t", $actualTestDuration.ToString()
        "-an"  # 测试时忽略音频
    )
    
    $testPass2Args = @(
        @($baseOutputArgs)
        "-t", $actualTestDuration.ToString()
        "-an"  # 测试时忽略音频
        "-f", "matroska"
    )
    
    try {
        Write-Host "  [测试编码] 使用两遍编码测试${actualTestDuration}秒片段..."
        $success = Start-TwoPassEncoding -InputFile $InputFilePath -OutputFile $TempFilePath `
            -Pass1OutputArgs $testPass1Args -Pass2OutputArgs $testPass2Args
        
        if (-not $success) {
            Write-Warning "测试编码失败: $InputFilePath"
            return -1
        }
        
        if (-not (Test-Path -Path $TempFilePath -PathType Leaf)) {
            Write-Warning "未生成测试文件: $TempFilePath"
            return -1
        }
        
        # 获取测试文件的比特率
        $testInfo = Get-VideoInfo "$TempFilePath"
        if (-not $testInfo) {
            Write-Warning "无法解析测试文件信息: $TempFilePath"
            return -1
        }
        
        $testBitrate = [double]$testInfo.Bitrate
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
        # 清理测试文件
        if (Test-Path -LiteralPath $TempFilePath -PathType Leaf) {
            Remove-Item -LiteralPath $TempFilePath -Force
        }
    }
}

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

#endregion

#region 脚本

$baseOutputArgs = @(
    "-c:v", "libsvtav1",
    "-crf", "35" # 0-63，0 为无损
    "-preset", "6" # 0-8，越高越快
)

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



# 获取要处理的文件
$allFiles = Get-ChildItem -LiteralPath $InputDirectory -File -Recurse:$Recursive | Where-Object {
    $_.Extension -in $videoExtensions
}


Write-Host "找到 $($allFiles.Count) 个视频文件"

# 如果没有找到符合条件的文件，退出
if ($allFiles.Count -eq 0) {
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


foreach ($inputFile in $allFiles) {
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
    Write-Host "[$processedCount/$($allFiles.Count)] 处理: $($inputFile.Name)"
    Write-Host "  输入: $($inputFile.FullName)"
    Write-Host "  输出: $outputFile"
    
    # 检查是否已存在最终输出文件
    if ((-not $Force) -and (Test-Path -Path $outputFile -PathType Leaf)) {
        Write-Host "  [跳过] 输出文件已存在"
        $skippedCount++
        continue
    }
    
    # 检查是否存在临时文件（可能是上次中断留下的）
    if (Test-Path -LiteralPath $outputTempFile -PathType Leaf) {
        Write-Host "  [警告] 发现未完成的临时文件，将删除"
        Remove-Item -LiteralPath $outputTempFile -Force
    }
    
    Write-Host "  [信息] 评估是否值得转码..."
    $worthTranscoding = Test-WorthTranscoding -FilePath $inputFile.FullName
        
    if ($worthTranscoding) {
        Write-Host "  [信息] 文件值得转码，开始两遍编码转换为AV1..."
        
        # 构建两遍编码的参数
        $pass1Args = @(
            @($baseOutputArgs)
        )
        
        $pass2Args = @(
            @($baseOutputArgs)
            "-map", "0"  # 映射所有流
            "-c:a", "copy"  # 复制音频流
            "-c:s", "copy"  # 复制字幕流
            "-c:d", "copy"  # 复制数据流
            "-f", "matroska"
        )
        
        # 使用两遍编码
        $success = Start-TwoPassEncoding -InputFile $inputFile.FullName -OutputFile $outputFile `
            -Pass1OutputArgs $pass1Args -Pass2OutputArgs $pass2Args
        
        if ($success) {
            Write-Host "  [成功] 两遍编码完成"
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
            Write-Host "  [失败] 两遍编码失败"
            $failedCount++
            
            # 清理失败的文件
            if (Test-Path -LiteralPath $outputFile -PathType Leaf) {
                Remove-Item -LiteralPath $outputFile -Force
            }
        }
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
            $elapsed.TotalSeconds * $allFiles.Count / $processedCount
        }
        else { 0 }
        $remaining = [timespan]::FromSeconds($estimatedTotal - $elapsed.TotalSeconds)
        
        Write-Host "  进度: $processedCount/$($allFiles.Count) | 已用时: $($elapsed.ToString('hh\:mm\:ss')) | 预计剩余: $($remaining.ToString('hh\:mm\:ss'))"
        continue
    }
    else {
        Write-Host "  [信息] 文件不值得转码，重新封装为MKV（不重新编码）"
        
        $outputTempFile = "$outputFile.tmp"
        # 使用重新封装（不重新编码）
        $remuxArgs = @(
            "-y",
            "-i", "`"$($inputFile.FullName)`"",
            "-map", "0",  # 映射所有流
            "-c", "copy",  # 复制所有流，不重新编码
            "-f", "matroska",
            "`"$outputTempFile`""
        )
        
        try {
            $process = Start-Process -PassThru -FilePath ffmpeg -ArgumentList $remuxArgs -NoNewWindow
            $process.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::BelowNormal
            $process.WaitForExit()

            if ($process.ExitCode -eq 0) {
                Write-Host "  [成功] 重新封装完成"
                $convertedCount++
                Move-Item -LiteralPath $outputTempFile -Destination $outputFile -Force:$Force
                
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
          
                Write-Host "  [失败] ffmpeg错误，退出码: $($process.ExitCode)"
                $failedCount++
            }
        }
        catch {
            Write-Host "  [错误] 重新封装过程中发生异常: $_"
            $failedCount++
            if ($process -and -not ($process.HasExited)) {
                $process.Kill()
            }
            if (Test-Path -LiteralPath $outputTempFile) {
                Remove-Item -Force -LiteralPath $outputTempFile
            }
        }
    }
    
    # 显示进度
    $elapsed = (Get-Date) - $startTime
    $estimatedTotal = if ($processedCount -gt 0) {
        $elapsed.TotalSeconds * $allFiles.Count / $processedCount
    }
    else { 0 }
    $remaining = [timespan]::FromSeconds($estimatedTotal - $elapsed.TotalSeconds)
    
    Write-Host "  进度: $processedCount/$($allFiles.Count) | 已用时: $($elapsed.ToString('hh\:mm\:ss')) | 预计剩余: $($remaining.ToString('hh\:mm\:ss'))"
}

# 输出统计信息
$endTime = Get-Date
$totalTime = $endTime - $startTime

Write-Host ""
Write-Host "=" * 50
Write-Host "转换完成！"
Write-Host "总文件数: $($allFiles.Count)"
Write-Host "已转换: $convertedCount"
Write-Host "已移动: $movedCount"
Write-Host "跳过: $skippedCount"
Write-Host "失败: $failedCount"
Write-Host "总用时: $($totalTime.ToString('hh\:mm\:ss'))"
Write-Host "=" * 50

#endregion
