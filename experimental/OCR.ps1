Param (
    [Parameter(
        Mandatory,
        Position = 0,
        HelpMessage = "image file path"
    )]
    [string]
    $Path,

    [switch]
    $ToClipboard,
    [switch]
    $ImageToClipboard
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$env:Path = "${env:Path};${env:ProgramFiles}\Tesseract-OCR;${env:ProgramFiles(x86)}\Tesseract-OCR;"

$tmpImage = [System.IO.Path]::GetTempFileName()+".png"

& magick.exe $Path -normalize $tmpImage

[String]$result = & tesseract.exe -l eng+jpn+chi_sim $tmpImage -
Remove-Item $tmpImage
if ($LASTEXITCODE) {
    exit $LASTEXITCODE
}

$result = $result.Replace("`f", "`n`n").Trim()

if ($ToClipboard) {
    Add-Type -AssemblyName PresentationCore
    $img = [System.Windows.Media.Imaging.BitmapImage]::new($Path)
    $do = [System.Windows.DataObject]::new()
    if ($ImageToClipboard) {
        $do.SetImage($img)
    }
    $do.SetText($result.Trim())
    $do.SetData("HTML Format", @"
<html>
<body>
<!--StartFragment-->
<img src=`"file:///$Path`"><br>
"@ + @(If ($result) {
                @"
文本识别：<br>
$($result.Replace("`n", "<br>"))<br>
"@             
            }
            Else { "" }
        ) + @"
文件名：<br>
$(Split-Path -Leaf $Path)<br>
分辨率：<br>
$([int]$img.Width)x$([int]$img.Height)
<!--EndFragment-->
</body>
</html>
"@)
    [System.Windows.Clipboard]::SetDataObject($do, $true)
}
else {
    $result
}
