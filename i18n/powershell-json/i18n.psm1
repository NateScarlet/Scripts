       
$Script:fallbackMessages = (Get-Content -Encoding utf8 "$PSScriptRoot/locales/en.json" | ConvertFrom-Json)
$Script:messages = $null

function Get-I18nTranslatedString() {
    [CmdletBinding()]
    param (
        [Parameter()]
        [string]
        $ID
    )
    if ($Script:messages."$ID") {
        return $Script:messages."$ID"
    }
    if ($Script:fallbackMessages."$ID") {
        return $Script:fallbackMessages."$ID"
    }
    return $ID
}

function Set-I18nLanguage() {
    [CmdletBinding()]
    param (
        [Parameter()]
        [string]
        $Language
    )
    $Script:messages = (Get-Content -Encoding utf8 "$PSScriptRoot/locales/$Language.json" | ConvertFrom-Json)
}


Export-ModuleMember -Function Get-I18nTranslatedString
Export-ModuleMember -Function Set-I18nLanguage
Set-Alias _ Get-I18nTranslatedString
Export-ModuleMember -Alias _
