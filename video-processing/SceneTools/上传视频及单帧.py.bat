# usr/bin/env python
# -*- coding=UTF-8 -*-
# uploadTool
# Version 0.1
'''
REM load py script from bat
@ECHO OFF & CHCP 936 & CLS
REM Read ini
REM Won't support same variable name in diffrent block
FOR /F "usebackq eol=; tokens=1,* delims==" %%a IN ("%~dp0path.ini") DO (
    IF NOT "%%b"=="" (
        SET "%%a=%%b"
    )
)

CALL :getPythonPath %NUKE%
START "uploadTool" %PYTHON% %0 %*
IF %ERRORLEVEL% == 0 (
    GOTO :EOF
) ELSE (
    ECHO.
    ECHO **ERROR** - NUKE path in path.ini not Correct.
    ECHO.
    EXPLORER path.ini
    PAUSE & GOTO :EOF
)
GOTO :EOF

:getPythonPath
SET "PYTHON="%~dp1python.exe""
GOTO :EOF
'''
import os
import sys
import re
from subprocess import call

# Read ini
os.chdir(os.path.dirname(__file__))

EP = None
IMAGE_FOLDER = None
NUKE = None
PROJECT = None
SCENE = None
SERVER = None
VIDEO_FOLDER = None

def readINI(ini_file='path.ini'):
    with open(ini_file, 'r') as ini_file:
        for line in ini_file.readlines():
            result = re.match('^([^;].*)=(.*)', line)
            if result:
                var_name = result.group(1)
                var_value = result.group(2)
                globals()[var_name] = var_value
                print('{}: {}'.format(var_name, var_value))
    print('')

readINI()
if EP:
    EP = 'EP' + EP.lstrip('EP')

# Startup
VERSION = 0.1
prompt_codec = 'gbk'
script_codec = 'UTF-8'
call(u'CHCP 936 & TITLE 上传工具_v{} & CLS'.format(VERSION).encode(prompt_codec), shell=True)

def print_(obj):
    print(str(obj).decode(script_codec).encode(prompt_codec))

if SERVER and PROJECT and EP and SCENE and (VIDEO_FOLDER or IMAGE_FOLDER):
    if VIDEO_FOLDER:
        video_dest = '\\'.join([SERVER, PROJECT, VIDEO_FOLDER, EP, SCENE])
    if IMAGE_FOLDER:
        image_dest = '\\'.join([SERVER, PROJECT, IMAGE_FOLDER, EP, SCENE])
else:
    print_('**错误**\tpath.ini中的集场或其他选项未设置, 必须先设置才能使用此工具。')
    call(u'EXPLORER path.ini')
    call('PAUSE', shell=True)
    exit()
    
print('')

# Display choice
print_('方案1:\t\t\t上传mov至: {video_dest}\n'
       '方案2:\t\t\t上传单帧至: {image_dest}\n'
       '方案3:\t\t\t上传mov和单帧(默认)\n'
       '\nCtrl+C\t直接退出'.format(video_dest=video_dest, image_dest=image_dest))
       
try:
    choice = call(u'CHOICE /C 123 /T 15 /D 3 /M "选择方案"'.encode(prompt_codec))
except KeyboardInterrupt:
    exit()

isUploadVideo = False
isUploadImage = False
if choice == 1:
    isUploadVideo = True
elif choice == 2:
    isUploadImage = True
elif choice == 3:
    isUploadVideo = True
    isUploadImage = True
else:
    exit()

# Define function
def uploadVideo():
    if os.path.exists(os.path.dirname(video_dest)):
        if not os.path.exists(video_dest):
            os.mkdir(video_dest)
        call(['XCOPY', '/Y', '/D', '/I', '/V', 'mov\\*.mov', video_dest])
        call(['XCOPY', '/Y', '/D', '/I', '/V', 'mov\\burn-in\\*.mov', video_dest+'\\burn-in'])
    else:
        print_('**错误** 视频上传文件夹不存在, 将不会上传。')

def uploadImage():
    if os.path.exists(os.path.dirname(image_dest)):
        if not os.path.exists(image_dest):
            os.mkdir(image_dest)
        call(['XCOPY', '/Y', '/D', '/I', '/V', 'images\\*.jpg', image_dest])
    else:
        print_('**错误** 图片上传文件夹不存在, 将不会上传。')

# Main
try:
    if isUploadVideo:
        uploadVideo()
    if isUploadImage:
        uploadImage()
    choice = call(u'CHOICE /t 15 /d y /m "15秒后此窗口自动关闭"'.encode(prompt_codec))
    if choice == 2:
        call('PAUSE', shell=True)
    else:
        exit()
except SystemExit as e:
    exit(e)
except:
    import traceback
    traceback.print_exc()
    call('PAUSE', shell=True)
