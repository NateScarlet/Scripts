SET UserDir=Z:\SNJYW\Comp\mov\EP02\05
::REM 多个文件夹名用逗号分隔,格式为 "文件夹1","文件夹2",...
FOR /R "Z:\SNJYW\Comp\mov\EP02\05\" %%i in (*) do (
ECHO %%~ni
::MKLINK %%~ni %%i
)
PAUSE