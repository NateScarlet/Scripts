@echo off
echo !将删除名称为skypee;27272;autorun.inf;4c4;a9a9a;383的文件夹或文件
pause
cd %~d0\
echo !终止病毒进程
taskkill /F /FI "IMAGENAME eq AutoIt*"
echo !删除U盘病毒文件
attrib -s -h -a -r skypee
attrib -s -h -a -r 27272
attrib -s -h -a -r autorun.inf
attrib -s -h -a -r 4c4
attrib -s -h -a -r a9a9a
attrib -s -h -a -r 383
rd skypee /s /q
rd 27272 /s /q
rd 4c4 /s /q
rd a9a9a /s /q
rd 383 /s /q
del autorun.inf /f /q 
echo !建立病毒同名文件占位
del skypee /f /q 
cd.>skypee
del 27272 /f /q
cd.>27272
del 4c4 /f /q
cd.>4c4
del a9a9a /f /q
cd.>a9a9a
del 383 /f /q
cd.>383
rd autorun.inf /s /q
md autorun.inf
md autorun.inf\防毒用_勿删
attrib +s +h +a +r skypee
attrib +s +h +a +r 27272
attrib +s +h +a +r 4c4
attrib +s +h +a +r a9a9a
attrib +s +h +a +r 383
attrib +s +h +a +r autorun.inf
echo !删除C盘病毒文件
attrib -s -h -a -r C:\Google
attrib -s -h -a -r C:\Skypee
rd C:\Google /s /q
rd C:\Skypee /s /q
echo !建立C盘病毒同名文件占位
del C:\Google /f /q
cd.>C:\Google
del C:\Skypee /f /q
cd.>C:\Skypee
attrib +s +h +a +r C:\Google
attrib +s +h +a +r C:\Skypee
echo !删除启动文件夹的脚本文件
cd /d %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
attrib -s -h -a -r *.js
del *.js /f /q
echo !清1126新病毒
::终止进程
taskkill /fi "imagename eq fun.exe" /f
taskkill /fi "imagename eq dc.exe" /f
taskkill /fi "imagename eq sviq.exe" /f
::设置当前目录
cd /d c:\
cd c:\Windows
::删除病毒文件
attrib -s -h -a -r fun.exe
attrib -s -h -a -r dc.exe
attrib -s -h -a -r sviq.exe
del dc.exe /f /q
del sviq.exe /f /q
del fun.exe /f /q
::建立病毒同名文件占位
rd fun.exe /s /q
md fun.exe
md fun.exe\防毒用_勿删
rd dc.exe /s /q
md dc.exe
md dc.exe\防毒用_勿删
rd sviq.exe /s /q
md sviq.exe
md sviq.exe\防毒用_勿删
attrib +s +h +a +r fun.exe
attrib +s +h +a +r dc.exe
attrib +s +h +a +r sviq.exe
echo —————————————————————————————
echo ——如果显示拒绝访问请右键管理员权限重新运行一遍此文件——
echo —————————————————————————————
pause