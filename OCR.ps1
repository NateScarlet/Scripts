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

$result = & "${env:ProgramFiles}\Tesseract-OCR\tesseract.exe" $Path -
if ($LASTEXITCODE) {
    exit $LASTEXITCODE
}

if ($ToClipboard) {
    Set-Clipboard $result
} else {
    $result
}
