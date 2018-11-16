Set-Alias VBoxManage "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe"
Set-Alias VBoxGUI "C:\Program Files\Oracle\VirtualBox\VirtualBox.exe"

function Start-VM($Name = 'default') {
    VBoxManage startvm --type headless $Name
}
function Stop-VM($Name = 'default') {
    VBoxManage controlvm $Name savestate
}