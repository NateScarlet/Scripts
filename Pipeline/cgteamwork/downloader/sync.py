# usr/bin/env python
# -*- coding=UTF-8 -*-

import os
import sys
import locale
from config import Config
from subprocess import call

CGTW_PATH = r"C:\cgteamwork\bin\base"
sys.path.append(CGTW_PATH)
import cgtw

SYS_CODEC = locale.getdefaultlocale()[1]

def copy(src, dst):
    cmd = u'XCOPY /Y /V /D "{}" "{}"'.format(os.path.normcase(unicode(src)), unicode(dst)).encode(SYS_CODEC)
    #print(cmd)
    call(cmd)

class Sync(Config):
    def __init__(self):
        super(Sync, self).__init__()
        self._tw = cgtw.tw()

    def is_login(self):
        ret = self._tw.sys().get_socket_status()
        return ret
        
    def check_login(self):
        if not self.is_login():
            raise LoginError
    
    def get_file_list(self):
        self.check_login()
        self.config['video_list'] = []
        path_field_name = 'shot_task.submit_file_path'

        self._task_module = self._tw.task_module(self.config['DATABASE'], self.config['MODULE'])
        initiated = self._task_module.init_with_filter([['shot_task.pipeline', '=', self.config['PIPELINE']]])
        if not initiated:
            print(u'找不到对应流程: {}'.format(self.config['PIPELINE']).encode(SYS_CODEC))
            return False

        items = self._task_module.get([path_field_name, 'shot.shot'])
        for i in items:
            if i['shot.shot'] and i['shot.shot'].startswith(self.config['SHOT_PREFIX']):
                path_field_value = i[path_field_name]
                if path_field_value:
                    self.config['video_list'] += eval(path_field_value)['path']

    def download_videos(self):
        for i in self.config['video_list']:
            copy(i, self.config['DEST'])

class IDError(Exception):
    def __init__(self, *args):
        self.message = args

    def __str__(self):
        return u'找不到对应条目:{}'.format(self.message).encode(SYS_CODEC)


class LoginError(Exception):
    def __str__(self):
        return u'CGTeamWork服务器未连接'.encode(SYS_CODEC)
