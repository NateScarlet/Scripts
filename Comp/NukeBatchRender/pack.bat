CD /D "%UserProfile%"
MKDIR NukeBatchRender
CD NukeBatchRender

pyinstaller.exe -F "%~dp0NukeBatchRender.py"

CD dist
"C:\Program Files\7-Zip\7z.exe" a -r0 "..\Nuke批渲染_v.zip" "*"
CD ..
EXPLORER %CD%