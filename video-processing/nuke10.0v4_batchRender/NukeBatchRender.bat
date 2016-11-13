@ECHO off
SET NUKE="C:\Program Files\Nuke10.0v4\Nuke10.0.exe"
SET serverZ=\\192.168.1.4\f
CHOICE /T 15 /D n /M "本地渲染"
IF "%ERRORLEVEL%" EQU "1" SET isLocalRender=Y
MKDIR "%~dp0RenderLog" 2>nul
IF /I "%isLocalRender%" EQU "Y" (
    ECHO 将进行本地化渲染
    NET USE Z: /DELETE 2>nul
    SUBST Z: "D:\Cache\Nuke\localize\Z_"
)
SET renderTime=%date:~2,2%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%
SETLOCAL enabledelayedexpansion
FOR %%i in ("%~dp0\*.nk") do (
    @IF /I "%isLocalRender%" EQU "Y" "%~dp0localiseFootage.bat" %%~i
	SET startTime=!time:~0,8!
    @IF /I "%~1" NEQ "-PROXY" (
        ECHO.
        ECHO 全尺寸渲染 %%~nxi 
        ECHO.
        %NUKE% -x -f --cont "%%~i" 2>>"%~dp0Renderlog\Renderlog_%renderTime%.txt"
        SET finishTime=!time:~0,8!
        ECHO !date! !startTime! !finishTime!	%%~ni >>"%~dp0Renderlog\Renderlog_%renderTime%.txt"
        )ELSE (
        ECHO.
        ECHO 代理模式渲染 %%~nxi
        ECHO.
        %NUKE% -x -p --cont "%%~i" 2>>"%~dp0Renderlog\Renderlog_%renderTime%.txt"
        SET finishTime=!time:~0,8!        
        ECHO !date! !startTime! !finishTime!	%%~ni^(代理模式^) >>"%~dp0Renderlog\Renderlog_%renderTime%.txt"
        )    
)
IF /I %isLocalRender% EQU Y (
    SUBST /D Z:
    NET USE Z: "%severZ%" /PERSISTENT:YES
)
ECHO !time:~0,8! 渲染完成
START "%~dp0Renderlog\Renderlog_%renderTime%.txt"
EXIT