@ECHO OFF
SET severDir=\\192.168.1.4\f
SET localDir=%NUKE_TEMP_DIR%\localize\Z_
SET agrv1=%~n1%
FOR /F "delims=_|. tokens=1-4" %%i in ("%agrv1%") do (
    SET project=%%i
    SET ep=%%j
    SET sc=%%k
    SET shot=%%l
)
REM SETLOCAL enalbeDelayedExpansion
CALL SET "dirName=%%agrv1:%project%_=%%"
ECHO.
ECHO 工程:%project% 集:%ep% 场:%sc% 镜头:%shot%
ECHO.
ECHO 将服务器素材下载到本地...
MKDIR "%localDir%\%project%\Render\%ep%\%sc%\%dirName%" 2>nul
ECHO Render\%ep%\%sc%\%dirName%
ECHO N | XCOPY /D /S "%severDir%\%project%\Render\%ep%\%sc%\%dirName%\*" "%localDir%\%project%\Render\%ep%\%sc%\%dirName%" 2>nul
MKDIR "%localDir%\%project%\FX\%ep%\%sc%\%dirName%" 2>nul
ECHO FX\%ep%\%sc%\%dirName%
ECHO N | XCOPY /D /S "%severDir%\%project%\FX\%ep%\%sc%\%dirName%\*" "%localDir%\%project%\FX\%ep%\%sc%\%dirName%" 2>nul
ECHO 素材下载完毕
ECHO.
REM PAUSE