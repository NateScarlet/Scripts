setlocal enabledelayedexpansion
for %%i in (1,1,10) do (
	@ping 127.0.0.1 -n 3 >nul 
	@echo !time!
)
pause