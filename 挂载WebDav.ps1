$DAV_URL = "https://example.com/dav" 
$DEVICENAME = "V:"

# Version: 2021.01.08

$ErrorActionPreference = "Stop"

Add-Type –AssemblyName PresentationFramework
Add-Type –AssemblyName PresentationCore
Add-Type –AssemblyName WindowsBase

if ((Get-Service WebClient).StartType -eq 'Disabled') {
    if ([System.Windows.MessageBox]::Show("使用管理员权限启用 WebClient 服务?", "WebClient 服务被禁用", "YesNo", "Question") -eq "Yes") {
        $process = Start-Process -Wait -PassThru -Verb RunAs -FilePath PowerShell -ArgumentList $(
            "-Version", "2", 
            "-NoProfile", 
            "-Sta"
            "-Command", @'
$srv = (Get-Service WebClient)
$srv | Set-Service -StartupType 'Automatic'
$srv.Start()
'@)
        if ($process.ExitCode) {
            Throw "启动 WebClient 服务失败"   
        }
    }
    elseif ((Get-Service WebClient).Status -eq 'Stopped') {
        return
    }

}


$mainWindow = [Windows.Markup.XamlReader]::Load( (New-Object System.Xml.XmlNodeReader ([xml]@"
<Window
  xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
  xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
  Title="挂载WebDav" Topmost="True" Width="280" Height="280">
  <StackPanel Margin="5">
      <Label Content="服务器地址"/>
      <TextBox x:Name="url" Height="23" TextWrapping="Wrap" Text="$DAV_URL"/>
      <Label Content="挂载盘符"/>
      <TextBox x:Name="deviceName" Height="23" TextWrapping="Wrap" Text="$DEVICENAME"/>
      <Label Content="用户名"/>
      <TextBox x:Name="username" Height="23" TextWrapping="Wrap" Text="$env:username"/>
      <Label Content="密码"/>
      <PasswordBox x:Name="password"/>
      <CheckBox x:Name="isAutoMount" Content="登录时自动挂载" IsChecked="True"/>
      <Button x:Name="ok" Content="确定" IsDefault="True"/>
  </StackPanel>
</Window>
"@)) )



$mainWindow.Content.FindName('ok').add_Click( {
        if ($mainWindow.Content.FindName("url").Text -eq '') {
            $mainWindow.Content.FindName("url").Focus()
            [System.Windows.MessageBox]::Show("服务器地址不可为空", "验证错误")
            return
        }
        if ($mainWindow.Content.FindName("username").Text -eq '') {
            $mainWindow.Content.FindName("username").Focus()
            [System.Windows.MessageBox]::Show("用户名不可为空", "验证错误")
            return
        }
        if ($mainWindow.Content.FindName("password").Password -eq '') {
            $mainWindow.Content.FindName("password").Focus()
            [System.Windows.MessageBox]::Show("密码不可为空", "验证错误")
            return
        }
        $mainWindow.DialogResult = $true
        $mainWindow.Close()
    }
)

[void]$mainWindow.Content.FindName("password").Focus()
if ($mainWindow.ShowDialog() -ne $true) {
    return
}

$url = [uri]$mainWindow.Content.FindName('url').Text
$username = $mainWindow.Content.FindName('username').Text
$password = $mainWindow.Content.FindName('password').Password
$deviceName = $mainWindow.Content.FindName('deviceName').Text
$isAutoMount = $mainWindow.Content.FindName("isAutoMount").IsChecked

function Invoke-NativeCommand {
    "+ $args".Replace("$password", "******")
    $command = $args[0]
    $arguments = $args[1..($args.Length)]
    & $command @arguments
    if (!$?) {
        Throw "exit code ${LastExitCode}: ${args}".Replace("$password", "******")
    }
}

"映射文件盘符至 ${deviceName}"

Invoke-NativeCommand chcp.com 936 | Out-Null
Invoke-NativeCommand net use $deviceName $url /PERSISTENT:NO /USER:$username $password

if ($isAutoMount) {
    "设置开机自动挂载"

    $startupScriptPath = "${env:Appdata}\Microsoft\Windows\Start Menu\Programs\Startup\map-drive-$($deviceName -replace ":").cmd"
    Set-Content -Path "$startupScriptPath" ((@'
@echo off
PowerShell -Version 2 -NoProfile -Sta -Command "Get-Content '%~dpnx0' -Encoding UTF8 | Select-Object -Skip 5 | Out-String | Invoke-Expression"
IF ERRORLEVEL 1 PAUSE
GOTO :EOF

# Version: 2021.01.04

$ErrorActionPreference = "Stop"

function Convert-SecureStringToText {
    Param
    (
        [Parameter(Mandatory=$true, ValueFromPipeline=$true, Position=0)]
        [System.Security.SecureString]
        $Password
    )
  
    $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($Password)
    [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($BSTR)
}

'@ + @"
`$url = [uri]'$url'
`$deviceName = '$deviceName'
`$username = '$username'
`$password = '$(ConvertTo-SecureString $password -AsPlainText -Force | ConvertFrom-SecureString)' | ConvertTo-SecureString | Convert-SecureStringToText

"@ + @'
function Invoke-NativeCommand {
    "+ $args".Replace("$password", "******")
    $command = $args[0]
    $arguments = $args[1..($args.Length)]
    & $command @arguments
    if (!$?) {
        Throw "exit code ${LastExitCode}: ${args}".Replace("$password", "******")
    }
}

Invoke-NativeCommand chcp.com 936 | Out-
if ((Get-Service WebClient).StartType -eq 'Disabled') {
    Throw "WebClient 服务被禁用，无法挂载"
}
Invoke-NativeCommand net use $deviceName $url /PERSISTENT:NO /USER:$username $password

'@) -replace "`r?`n", "`r`n") 
    "创建: $startupScriptPath"
}

