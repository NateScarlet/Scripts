# -*- coding=UTF-8 -*-

import os
import sys
import tempfile
import json
import subprocess

from pymel.all import *


VERSION = 0.1
CGTW_PATH = 'C:\\cgteamwork'

class CGTeamWork(object):
    database = u'proj_big'
    config = {
                'SERVER': u'Z:\\CGteamwork_Test', 
                'SHOT': '',
                'DATABASE': 'proj_big',
                'ASSET_MODULE': 'asset',
                'SHOT_TASK_MODULE': 'shot_task',
                'PIPELINE': u'合成',
                'video_list': [],
             }

    def __init__(self):
        self.check_install()
        
        self.get_shot_name()
        self.get_namespaces()

    def check_install(self):
        if not os.path.exists(CGTW_PATH):
            error(u'CGTeamWork路径不存在: {}'.format(CGTW_PATH).encode('UTF-8'))

    def get_shot_name(self):
        self.config['SHOT'] = os.path.splitext(sceneName().basename())[0]

    def get_namespaces(self):
        self.config['NAMESPACES'] = listNamespaces()

    @classmethod
    def show_window(cls, refresh=False):
        _window_name = 'CGTeamWork'

        if refresh:
            deleteUI(_window_name)
        
        if window(_window_name, exists=True):
            showWindow(_window_name)
            return True

        win = window(_window_name)
        rowColumnLayout( numberOfColumns=2, columnAttach=(1, 'right', 0), columnWidth=[(1, 100), (2, 250)] )
        text(label=u'项目数据库')
        textField('database', text=u'proj_big')
        win.show()
        return win
        
    def call_script(self):
        if '__file__' in globals():
            script = os.path.join(os.path.dirname(__file__), 'cgtw_link.py')
        else:
            script = r"D:\Users\zhouxuan.WLF\CloudSync\Scripts\Maya\wlf\cgtw_link.py"
        python = os.path.join(CGTW_PATH, 'python\\python.exe')

        with tempfile.NamedTemporaryFile(delete=False) as f:
            _tempfile = f.name
            json.dump(self.config, f, indent=4, sort_keys=True)
        cmd = '"{python}" -E -s "{script}" "{temp}"'.format(python=python, script=script, temp=f.name)
        print(cmd)
        print(subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT))
        os.remove(_tempfile)

if __name__ == '__main__':
    try:
        CGTeamWork().call_script()
    except SystemExit as e:
        exit(e)
    except:
        import traceback
        traceback.print_exc()