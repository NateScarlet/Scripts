Param (
    [Parameter(
        Mandatory,
        Position = 0,
        HelpMessage = "image file path"
    )]
    [string]
    $Path,

    [switch]
    $ToClipboard
)

[String]$result = & "${env:ProgramFiles}\Tesseract-OCR\tesseract.exe" $Path -
if ($LASTEXITCODE) {
    exit $LASTEXITCODE
}

$result = $result.Replace("`f", "`n`n").Trim()

if ($ToClipboard) {
    Add-Type -AssemblyName PresentationCore
    $img = [System.Windows.Media.Imaging.BitmapImage]::new($Path)
    $do = [System.Windows.DataObject]::new()
    $do.SetImage($img)
    $do.SetText($result.Trim())
    $do.SetData("HTML Format", @"
<img src=`"file:///$Path`">
<dl>
"@ + @(If ($result) {
                @"
    <dt>文本识别</dt>
    <dd>$result</dd>
"@             
            }
            Else { "" }
        ) + @"
    <dt>文件名</dt>
    <dd>$(Split-Path -Leaf $Path)</dd>
    <dt>分辨率</dt>
    <dd>$([int]$img.Width)x$([int]$img.Height)</dd>
</dl>
"@)
    [System.Windows.Clipboard]::SetDataObject($do, $true)
}
else {
    $result
}
