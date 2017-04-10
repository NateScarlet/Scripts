# usr/bin/env python
# -*- coding=UTF-8 -*-
# Nuke Batch Render
# Version 2.02
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
START "NukeBatchRender" %PYTHON% %0 %*
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
import logging
import logging.handlers
import shutil
import time
import datetime
from subprocess import call, Popen

os.chdir(os.path.dirname(__file__))

# Set logger
LOG_FILENAME = u'Nuke批渲染.log'
logfile = open(LOG_FILENAME, 'a')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.handlers.TimedRotatingFileHandler(LOG_FILENAME, when='D', backupCount=7)
formatter = logging.Formatter('[%(asctime)s]\t%(levelname)10s:\t%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Read ini

NUKE = None

def readINI(ini_file='path.ini'):
    with open(ini_file, 'r') as ini_file:
        for line in ini_file.readlines():
            result = re.match('^([^;].*)=(.*)', line)
            if result:
                var_name = result.group(1)
                var_value = result.group(2)
                globals()[var_name] = var_value
                logger.debug('{}: {}'.format(var_name, var_value))
    print('')

readINI()

# Startup
VERSION = 2.02
prompt_codec = 'gbk'
script_codec = 'UTF-8'
call(u'CHCP 936 & TITLE Nuke批渲染_v{} & CLS'.format(VERSION).encode(prompt_codec), shell=True)
render_time = time.strftime('%y%m%d_%H%M')

# Define function

def print_(obj):
    print(str(obj).decode(script_codec).encode(prompt_codec))

class nukeBatchRender(object):
    def __init__(self, dir=os.getcwd()):
        self.file_list = None

    def getFileList(self, dir=os.getcwd()):
        file_list = list(i for i in os.listdir(dir) if i.endswith('.nk'))
        self.file_list = file_list
        if file_list:
            print_('将渲染以下文件:')
            for file in file_list:
                print_('\t\t\t{}'.format(file))
                logger.debug (u'发现文件:\t{}'.format(file))
            print_('总计:\t{}\n'.format(len(file_list)))
            logger.debug(u'总计:\t{}'.format(len(file_list)))
        return file_list
    
    def render(self, isProxyRender=False, isLowPriority=False):
        if not self.file_list:
            logger.warning(u'没有找到可渲染文件')
            return False
        logger.info(u'<开始批渲染>')
        for file in self.file_list:
            print_('## [{}/{}]\t{}'.format(self.file_list.index(file) + 1, len(self.file_list), file))
            start_time = datetime.datetime.now()
            logger.info(u'开始渲染:\t{}'.format(file))
            locked_file = file + '.lock'
            
            # lock file
            shutil.copyfile(file, locked_file)
            file_archive_folder = 'ArchivedRenderFiles\\' + render_time
            file_archive_dest = '\\'.join([file_archive_folder, file])
            if not os.path.exists(file_archive_folder):
                os.makedirs(file_archive_folder)
            if os.path.exists(file_archive_dest):
                time_text = datetime.datetime.fromtimestamp(os.path.getctime(file_archive_dest)).strftime('%M%S_%f')
                os.rename(file_archive_dest, file_archive_dest + '.' + time_text)
            shutil.move(file, file_archive_dest)

            # Render
            if isProxyRender:
                proxy_switch = '-p'
            else:
                proxy_switch = '-f'
            if isLowPriority:
                priority_swith = ''
            else:
                priority_swith = '-c 8G --priority low'
            returncode = call(' '.join(i for i in [NUKE, '-x', proxy_switch, priority_swith, '--cont', locked_file] if i), stderr=logfile)
            if returncode:
                logger.error(u'渲染出错')
                os.rename(locked_file, file)
            else:
                os.remove(locked_file)
            end_time = datetime.datetime.now()
            total_seconds = (end_time-start_time).total_seconds()
            logger.info('总计耗时:\t{}'.format(secondsToStr(total_seconds)))
            if returncode:
                returncode_text = '退出码: {}'.format(returncode)
            else:
                returncode_text = '正常退出'
            logger.info('结束渲染:\t{}\t{}'.format(file, returncode_text))
        logger.info(u'<结束批渲染>')

def secondsToStr(seconds):
    ret = ''
    hour = seconds // 3600
    minute = seconds % 3600 // 60
    seconds = seconds % 60
    if hour:
        ret += '{}小时'.format(hour)
    if minute:
        ret += '{}分钟'.format(minute)
    ret += '{}秒'.format(seconds)
    return ret
        
# Display choice
logger.info('<启动>')
if not nukeBatchRender().getFileList():
    print_('**警告** 没有可渲染文件')
    logger.info(u'用户尝试在没有可渲染文件的情况下运行')
    call('PAUSE', shell=True)
    logger.info('<退出>')
    exit()

if os.path.exists('afterRender.bat'):
    print_('**提示** 将在渲染完成后自动运行afterRender.bat\n')
    
print_('方案1:\t\t\t制作模式(渲染时尽量保证其他程序流畅)(默认)\n'
       '方案2:\t\t\t午间模式(使用所有资源渲染, 其他程序可能会卡)\n'
       '方案3:\t\t\t夜间模式(全速渲染完后休眠)\n'
       '方案4:\t\t\t代理模式(流畅渲染小尺寸视频)\n'
       '\nCtrl+C\t直接退出\n')
       
try:
    choice = call(u'CHOICE /C 1234 /T 15 /D 1 /M "选择方案"'.encode(prompt_codec))
except KeyboardInterrupt:
    exit()

print('')
isLowPriority = False
isHibernate = False
isProxyRender = False
if choice == 1:
    isLowPriority = True
    logger.info('用户选择:\t制作模式')
elif choice == 2:
    logger.info('用户选择:\t午间模式')
elif choice == 3:
    isHibernate = True
    logger.info('用户选择:\t夜间模式')
elif choice == 4:
    isProxyRender = True
    isLowPriority = True
    logger.info('用户选择:\t代理模式')
else:
    exit()

# Main
try:
    autoclose = Popen(u'自动关闭崩溃提示.exe'.encode(prompt_codec))
    BatchRender = nukeBatchRender()
    while BatchRender.getFileList():
        BatchRender.render(isProxyRender, isLowPriority)
    if os.path.exists('afterRender.bat'):
        call('cmd /c afterRender.bat')
    autoclose.kill()
    Popen('EXPLORER {}'.format(LOG_FILENAME.encode(prompt_codec)))
    if isHibernate:
        choice = call(u'CHOICE /t 15 /d y /m "即将自动休眠"'.encode(prompt_codec))
        if choice == 2:
            call('PAUSE', shell=True)
        else:
            logger.info('计算机进入休眠模式')
            call(['SHUTDOWN', '/h'])
            call('PAUSE', shell=True)
    else:
        choice = call(u'CHOICE /t 15 /d y /m "此窗口将自动关闭"'.encode(prompt_codec))
        if choice == 2:
            call('PAUSE', shell=True)
    logger.info('<退出>')
    exit()
except SystemExit as e:
    exit(e)
except:
    import traceback
    traceback.print_exc()
    call('PAUSE', shell=True)
