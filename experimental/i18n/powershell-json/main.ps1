Import-Module "$PSScriptRoot\i18n.psm1"

_("test1")
_("test2")
_("test3")

Set-I18nLanguage "zh"

_("test1")
_("test2")
_("test3")
