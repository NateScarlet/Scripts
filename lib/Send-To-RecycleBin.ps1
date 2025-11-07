function Send-To-RecycleBin {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true, ValueFromPipeline = $true)]
        [string[]]$Path
    )
    
    begin {
        Add-Type -AssemblyName Microsoft.VisualBasic
    }
    
    process {
        foreach ($p in $Path) {
            $item = Get-Item -LiteralPath $p -ErrorAction SilentlyContinue
            if (!$item) {
                continue
            }
            if ($item.PSIsContainer) {
                # 处理目录
                [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory(
                    $item, 
                    'OnlyErrorDialogs', 
                    'SendToRecycleBin'
                )
            }
            else {
                # 处理文件
                [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile(
                    $item, 
                    'OnlyErrorDialogs', 
                    'SendToRecycleBin'
                )
            }
        }
    }
}
