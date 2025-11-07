# Delete-Old-Download.ps1

. "$PSScriptRoot/../lib/Send-To-RecycleBin.ps1"

$folder = (New-Object -ComObject Shell.Application).NameSpace('shell:Downloads').Self.Path
$cutoffDate = (Get-Date).AddDays(-90)

Write-Host "正在扫描下载文件夹中的旧文件..." -ForegroundColor Cyan
Write-Host "删除条件: 90天前（$($cutoffDate.ToString('yyyy-MM-dd'))）修改的文件" -ForegroundColor Yellow

Get-ChildItem $folder | Where-Object { 
    $_.LastWriteTime -lt $cutoffDate 
} | ForEach-Object { 
    Write-Host "将删除: $($_.Name) (修改于: $($_.LastWriteTime.ToString('yyyy-MM-dd')))" -ForegroundColor Yellow
    Send-To-RecycleBin $_
}

Write-Host "文件清理完成。" -ForegroundColor Cyan
