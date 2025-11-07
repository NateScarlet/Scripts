function Send-To-RecycleBin {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true, ValueFromPipeline = $true)]
        [object[]]$InputObject
    )
    
    begin {
        Add-Type -AssemblyName Microsoft.VisualBasic
    }
    
    process {
        foreach ($obj in $InputObject) {
            $item = $null
            if ($obj -is [System.IO.FileSystemInfo]) {
                $item = $obj
            }
            else {
                $item = Get-Item -LiteralPath $obj -ErrorAction SilentlyContinue
            }
            
            if (!$item -or !$item.Exists) {
                continue
            }
            
            
            if ($item.PSIsContainer) {
                [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory(
                    $item.FullName, 
                    'OnlyErrorDialogs', 
                    'SendToRecycleBin'
                )
            }
            else {
                [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile(
                    $item.FullName, 
                    'OnlyErrorDialogs', 
                    'SendToRecycleBin'
                )
            }
        }
    }
}
