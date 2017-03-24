
@ECHO OFF
CHCP 65001
SETLOCAL ENABLEDELAYEDEXPANSION
CD /D %~dp0
CLS

REM Set window title
SET "VERSION=1.971"
TITLE 生成色板后_上传v%VERSION%

REM Read ini
REM Won't support same variable name in diffrent block
FOR /F "usebackq eol=; tokens=1,* delims==" %%a IN ("path.ini") DO (
    IF NOT "%%b"=="" (
        SET "%%a=%%b"
    )
)

REM Set other
SET "SWITCH_RENDERING="%~dp0NukeBatchRendering.tmp""
SET "SWITCH_HIBER="%~dp0HiberAfterNukeBatchRender.tmp""
SET "CLOSE_ERROR_WINDOW="%~dp0CloseErrorWindow.exe""

:CheckEnv
REM Check if setting is correct
IF NOT EXIST "%~dp0\*.nk" (
    ECHO 错误 - 批处理所在文件夹不存在nk文件
    PAUSE&GOTO:EOF
)
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
    GOTO CheckEnv
)

:CheckSingleInstance
REM Check if is only rendering process
IF /I "%~1" EQU "-noHiberOption" (
    GOTO :OptionOfRendering
)
IF EXIST %SWITCH_RENDERING% (
    IF EXIST %SWITCH_HIBER% (
        ECHO 渲染完成后将休眠
        GOTO :OptionOfRendering
    ) ELSE (
        CHOICE /T 15 /C ac /D c /M "前一次渲染尚未正常结束,本次渲染中止(A)/继续(C)?"
        IF "!ERRORLEVEL!" EQU "1" (
            GOTO :EOF
        )
    )
) ELSE (
    ECHO. > %SWITCH_RENDERING%
)
IF EXIST %CLOSE_ERROR_WINDOW% (
    START "" %CLOSE_ERROR_WINDOW%
)

:OptionOfHiberAfterRender
REM Hiber Option
CHOICE /T 15 /D n /M "渲染完成后休眠"
ECHO.
IF "%ERRORLEVEL%" EQU "1" (
    ECHO 重要 - 此功能需要先设置默认字体，在弹出的新窗口标题栏右键－＞默认值－＞字体－＞新宋体，然后关闭此脚本重新运行
    ECHO 保持此窗口开启以实现渲染完毕自动休眠
    TITLE 休眠 - 渲染完成后
    START /WAIT POWERSHELL -Command "& '.\NukeBatchRender.bat'"  -noHiberOption"
    ECHO.
    CHOICE /T 15 /D y /M "15秒后休眠"
    IF ERRORLEVEL 2 GOTO:EOF
    SHUTDOWN /H
    GOTO:EOF
)

:OptionOfRendering
REM Render Options

REM Display info
ECHO 渲染时使用的NUKE路径: %NUKE%
ECHO 本地缓存时使用的Z盘网络路径: %serverZ%
ECHO.
ECHO 提示 - 可以编辑path.ini来设置路径
ECHO.

REM Ask render size
ECHO 输出尺寸:
CHOICE /T 15 /C pf /D f /M "代理(P)/全尺寸(F)"
IF "!ERRORLEVEL!" EQU "1" SET "isProxyRender=TRUE"
IF "!ERRORLEVEL!" EQU "2" SET "isProxyRender=FALSE"

REM Ask render priority
ECHO.
ECHO 渲染进程优先级:
CHOICE /T 15 /C ln /D n /M "低(L)/普通(N)"
IF "%ERRORLEVEL%" EQU "1" SET "isLowPriority=TRUE"
IF "%ERRORLEVEL%" EQU "2" SET "isLowPriority=FALSE"

REM Set render log path
SET "renderTime=%date:~5,2%%date:~8,2%%date:~11,2%_%time:~0,2%%time:~3,2%"
IF NOT EXIST "%~dp0RenderLog" (
    MKDIR "%~dp0RenderLog"
)
SET "RenderLog="%~dp0RenderLog\RenderLog_%renderTime%.txt""

REM Move out proxy rendered file
IF /I "%isProxyRender%" NEQ "TRUE" (
    IF EXIST "%~dp0PorxyRenderedFiles\" (
        ECHO.
        ATTRIB -R "%~dp0*.nk"
        XCOPY /D "%~dp0PorxyRenderedFiles\*.nk" "%~dp0"
        DEL "%~dp0PorxyRenderedFiles\*.nk"
    )
)

:Render
REM Render
FOR %%i in ("%~dp0\*.nk") do (
	SET "startTime=!time:~0,8!"
	SET "triedTimes=0"
    :SingleRender
   	IF /I "%isProxyRender%" EQU "TRUE" (
	    REM Render in proxy size
	    ECHO.
        ECHO 代理模式渲染 %%~nxi
        ECHO.
        IF  /I "%isLowPriority%" EQU "TRUE" (
            ECHO --低优先级
            ECHO.
            %NUKE% -x -p -c 8G --cont --priority low "%%~i" 2>>%RenderLog%
        ) ELSE (
            %NUKE% -x -p --cont "%%~i" 2>>%RenderLog%
        )
        SET "finishTime=!time:~0,8!"
        ECHO !date! !startTime! !finishTime!	%%~ni^(代理模式^) >>%RenderLog%
        IF NOT EXIST "%~dp0PorxyRenderedFiles\" (
            MKDIR "%~dp0PorxyRenderedFiles\"
        )
        ATTRIB -R "%~dp0PorxyRenderedFiles\%%~nxi"
        MOVE /Y "%%~i" "%~dp0PorxyRenderedFiles\"
	) ELSE (
	    REM Render in full size
        ECHO.
        ECHO 全尺寸渲染 %%~nxi 
        ECHO.
        IF  /I "%isLowPriority%" EQU "TRUE" (
            ECHO --低优先级
            ECHO.
            %NUKE% -x -f -c 8G --cont --priority low "%%~i" 2>>%RenderLog%
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

REM Display renderlog
EXPLORER %RenderLog%

REM Execute afterrender script
IF EXIST %~dp0afterRender.bat% (
    START /WAIT POWERSHELL "& '%~dp0afterRender.bat%'"
)

REM Exiting
DEL %SWITCH_RENDERING%
GOTO:EOF

REM Function define
:RetryRender
IF ERRORLEVEL 1 (
    IF "!renderTimes!" LEQ "3" (
        SET /A renderTimes+=1
        GOTO:SingleRender
    )
)
GOTO:EOF