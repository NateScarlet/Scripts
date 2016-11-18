@ECHO OFF
SET "NUKE="C:\Program Files\Nuke10.0v4\Nuke10.0.exe""
ECHO NUKE路径: %Nuke%
SET "serverZ=\\192.168.1.4\f"
ECHO Z盘网络路径: %serverZ%
ECHO.
ECHO 提示 - 可以编辑此批处理文件来设置路径
ECHO.
REM
REM 在上方设置路径变量
REM
:设置选项
CHOICE /T 15 /D n /M "本地缓存渲染"
IF "%ERRORLEVEL%" EQU "1" SET "isLocalRender=TRUE"
SET "renderTime=%date:~2,2%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%"
IF NOT EXIST "%~dp0RenderLog" (
    MKDIR "%~dp0RenderLog"
)
IF /I "%isLocalRender%" EQU "TRUE" (
    IF NOT EXIST "%NUKE_TEMP_DIR%" (
        ECHO 错误 - 需要设置环境变量%NUKE_TEMP_DIR%^(末尾不要反斜杠^)
        ECHO 将不使用本地缓存渲染
        PAUSE
        SET "isLocalRender=FALSE"
        GOTO:渲染
    )
    ECHO 提示 - 将进行本地化渲染
    CALL "%~dp0all_localiseFootage.bat" "%serverZ%"
    IF EXIST "Z:\" (
        SUBST Z: /D >nul || NET USE Z: /DELETE 2>nul
        IF ERRORLEVEL 1 (        
            ECHO 错误 - 无法断开Z盘
            ECHO 将不使用本地缓存渲染
            SET "isLocalRender=FALSE"
            GOTO:Render
        )
    )
    SUBST Z: "%NUKE_TEMP_DIR%\localize\Z_"
)
SET "RenderLog="%~dp0RenderLog\RenderLog_%renderTime%.txt""
:Render
REM 渲染
SETLOCAL EnableDelayedExpansion
IF NOT EXIST "%~dp0\*.nk" (
    ECHO 错误 - 批处理所在文件夹不存在nk文件
    PAUSE&GOTO:EOF
)
FOR %%i in ("%~dp0\*.nk") do (
    @IF /I "%isLocalRender%" EQU "Y" "%~dp0localiseFootage.bat" %%~i 2>>%RenderLog%
	SET "startTime=!time:~0,8!"
    @IF /I "%~1" NEQ "-PROXY" (
        ECHO.
        ECHO 全尺寸渲染 %%~nxi 
        ECHO.
        %NUKE% -x -f --cont "%%~i" 2>>%RenderLog%
        SET "finishTime=!time:~0,8!"
        ECHO !date! !startTime! !finishTime!	%%~ni >>%RenderLog%
        IF NOT EXIST "%~dp0ArchivedRenderFiles\%rendertime%" (
            MKDIR "%~dp0ArchivedRenderFiles\%rendertime%"
        )
        MOVE "%%~i" "%~dp0ArchivedRenderFiles\%rendertime%\"
    )ELSE (
        ECHO.
        ECHO 代理模式渲染 %%~nxi
        ECHO.
        %NUKE% -x -p --cont "%%~i" 2>>%RenderLog%
        SET "finishTime=!time:~0,8!"        
        ECHO !date! !startTime! !finishTime!	%%~ni^(代理模式^) >>%RenderLog%
    )
)
ECHO [!time:~0,8!] 渲染完成
IF /I "%isLocalRender%" EQU "TRUE" (
    SUBST /D Z:
    NET USE Z: "%serverZ%" /PERSISTENT:YES
)
FOR /F "demils=" %%i in ('FORFILES /P %~dp0/Renderlog /D -30 ^| FINDSTR /I "RenderLog_.*\.txt") do (
    DEL %%i
)
EXPLORER %RenderLog%
EXIT