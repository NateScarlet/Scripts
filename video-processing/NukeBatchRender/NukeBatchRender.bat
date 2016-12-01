@ECHO OFF
CHCP 65001 > nul
TITLE Nuke批渲染v1.5
SETLOCAL EnableDelayedExpansion
REM 完成后休眠选项
IF /I "%~1" EQU "-noHiberOption" GOTO:StartUp
CHOICE /T 15 /D n /M "渲染完成后休眠"
ECHO.
IF "%ERRORLEVEL%" EQU "1" (
    ECHO 保持此窗口开启以实现渲染完毕自动休眠
    TITLE 休眠 - 渲染完成后
    START /WAIT POWERSHELL "& '%~0'" -noHiberOption
    ECHO.
    CHOICE /T 15 /D y /M "15秒后休眠"
    IF ERRORLEVEL 2 GOTO:EOF
    SHUTDOWN /h
    GOTO:EOF
)
:StartUp
REM
REM 在下方设置路径变量
REM
SET "NUKE="C:\Program Files\Nuke10.0v4\Nuke10.0.exe""
SET "serverZ=\\192.168.1.7\z"
REM
REM 在上方设置路径变量
REM
ECHO 渲染时使用的NUKE路径: %NUKE%
ECHO 本地缓存时使用的Z盘网络路径: %serverZ%
ECHO.
ECHO 提示 - 可以编辑此批处理文件头部来设置路径
ECHO.
:SettingCheck
REM 检查路径设置
FOR /F "delims=" %%i IN ("!NUKE!") DO SET "NUKE="%%~i""
FOR /F "delims=" %%i IN ("!serverZ!") DO SET "serverZ=%%~i"
IF NOT EXIST !NUKE! (
    ECHO 错误 - 文件内设置的路径不正确
    ECHO 请手动设置Nuke路径__从资源管理器将Nuke.exe拖进来即可
    SET /P "inputTemp=Nuke程序路径:"
    IF "!inputTemp!" NEQ "" (
        SET "NUKE=!inputTemp!"
        SET "inputTemp="
    )
    GOTO SettingCheck
)
CHOICE /T 15 /D n /M "素材缓存到本地后从缓存渲染"
IF "%ERRORLEVEL%" EQU "1" SET "isLocalRender=TRUE"
IF /I "%~1" EQU "-PROXY" (
    SET "isProxyRender=TRUE"
) ELSE (
    ECHO.
    ECHO 输出尺寸:
    CHOICE /T 15 /C pf /D f /M "代理(P)/全尺寸(F)"
    IF "!ERRORLEVEL!" EQU "1" SET "isProxyRender=TRUE"
    IF "!ERRORLEVEL!" EQU "2" SET "isProxyRender=FALSE"
)
ECHO.
ECHO 渲染进程优先级:
CHOICE /T 15 /C ln /D n /M "低(L)/普通(N)"
IF "%ERRORLEVEL%" EQU "1" SET "isLowPriority=TRUE"
IF "%ERRORLEVEL%" EQU "2" SET "isLowPriority=FALSE"
REM 为渲染日志作准备
SET "renderTime=%date:~5,2%%date:~8,2%%date:~11,2%_%time:~0,2%%time:~3,2%"
IF NOT EXIST "%~dp0RenderLog" (
    MKDIR "%~dp0RenderLog"
)
REM 断开Z盘映射并重新映射Z盘到缓存文件夹
IF /I "%isLocalRender%" EQU "TRUE" (
    IF NOT EXIST "%NUKE_TEMP_DIR%" (
        ECHO 错误 - 需要设置环境变量%NUKE_TEMP_DIR%^(末尾不要反斜杠^)
        ECHO 将不使用本地缓存渲染
        PAUSE
        SET "isLocalRender=FALSE"
        GOTO:Render
    )
    ECHO.
    ECHO 提示 - 将进行本地化渲染
    IF NOT EXIST "%~dp0localiseFootage.bat" (
        ECHO 找不到文件 - localiseFootage.bat
        ECHO 将不使用本地缓存渲染
        PAUSE
        SET "isLocalRender=FALSE"
        GOTO:Render
    )
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
    REM 调用LocaliseFootage.bat来缓存素材
    CALL "%~dp0LocaliseFootage.bat" "" "%serverZ%"
)
SET "RenderLog="%~dp0RenderLog\RenderLog_%renderTime%.txt""
:Render
REM 渲染
IF NOT EXIST "%~dp0\*.nk" (
    ECHO 错误 - 批处理所在文件夹不存在nk文件
    PAUSE&GOTO:EOF
)
FOR %%i in ("%~dp0\*.nk") do (
	SET "startTime=!time:~0,8!"
	SET "triedTimes=0"
    :SingleRender
   	IF /I "%isProxyRender%" EQU "TRUE" (
	    REM 代理渲染
	    ECHO.
        ECHO 代理模式渲染 %%~nxi
        ECHO.
        IF  /I "%isLowPriority%" EQU "TRUE" (
            ECHO --低优先级
            ECHO.
            %NUKE% -x -p --cont --priority low "%%~i" 2>>%RenderLog%
        ) ELSE (
            %NUKE% -x -p --cont "%%~i" 2>>%RenderLog%
        )
        SET "finishTime=!time:~0,8!"
        ECHO !date! !startTime! !finishTime!	%%~ni^(代理模式^) >>%RenderLog%
	) ELSE (
	    REM 全尺寸渲染
        ECHO.
        ECHO 全尺寸渲染 %%~nxi 
        ECHO.
        IF  /I "%isLowPriority%" EQU "TRUE" (
            ECHO --低优先级
            ECHO.
            %NUKE% -x -f --cont --priority low "%%~i" 2>>%RenderLog%
        ) ELSE (
            %NUKE% -x -f --cont "%%~i" 2>>%RenderLog%
        )
        SET "finishTime=!time:~0,8!"
        ECHO !date! !startTime! !finishTime!	%%~ni >>%RenderLog%
        IF NOT EXIST "%~dp0ArchivedRenderFiles\%rendertime%" (
            MKDIR "%~dp0ArchivedRenderFiles\%rendertime%"
        )
        MOVE "%%~i" "%~dp0ArchivedRenderFiles\%rendertime%\"
	)
)
ECHO [!time:~0,8!] 渲染完成
REM 重新映射回Z盘
IF /I "%isLocalRender%" EQU "TRUE" (
    SUBST /D Z:
    NET USE Z: "%serverZ%" /PERSISTENT:YES
)
REM 清理2个月前的日志
FOR /F "demils=" %%i in ('FORFILES /P %~dp0/Renderlog /D -30 ^| FINDSTR /I "RenderLog_.*\.txt") do (
    DEL %%i
)
EXPLORER %RenderLog%
GOTO:EOF
REM
:RetryRender
IF ERRORLEVEL 1 (
    IF "!renderTimes!" LEQ "3" (
        SET /A renderTimes+=1
        GOTO:SingleRender
    )
)
GOTO:EOF