# -*- coding=UTF-8 -*-

import os
import sys
import tempfile
import json
import subprocess
import locale

from pymel.all import *


VERSION = 0.12
CGTW_PATH = 'C:\\cgteamwork'
SYS_CODEC = locale.getdefaultlocale()[1]

class CGTeamWork(object):
    config = {
                'SERVER': u'Z:\\CGteamwork_Test', 
                'SHOT': '',
                'DATABASE': 'proj_big',
                'ASSET_MODULE': 'asset',
                'SHOT_TASK_MODULE': 'shot_task',
                'PIPELINE': u'Layout',
                'NAMESPACES': [],
                'REFERENCES': [],
             }

    def __init__(self):
        self.check_install()
        
        self.get_shot_name()
        self.get_namespaces()
        self.get_references()

    def check_install(self):
        if not os.path.exists(CGTW_PATH):
            error(u'CGTeamWork路径不存在: {}'.format(CGTW_PATH).encode('UTF-8').encode(SYS_CODEC))

    def get_shot_name(self):
        self.config['SHOT'] = os.path.splitext(sceneName().basename())[0]

    def get_namespaces(self):
        self.config['NAMESPACES'] = listNamespaces()
        
    def get_references(self):
        _reference_list = listReferences()
        _ret = []
        for i in _reference_list:
            _file = i.path
            _filename = os.path.splitext(os.path.basename(_file))[0]
            _ret.append(_filename)

        self.config['REFERENCES'] = _ret

    @classmethod
    def show_window(cls, refresh=False):
        _window_name = 'CGTeamWork'

        if window(_window_name, exists=True):
            if refresh:
                deleteUI(_window_name)
            else:
                showWindow(_window_name)
                return True

        win = window(_window_name)
        rowColumnLayout( numberOfColumns=2, columnAttach=(1, 'right', 0), columnWidth=[(1, 100), (2, 250)] )
        text(label=u'项目数据库')
        _database = textField('database', text=cls.config['DATABASE'])
        def _ok_button_pressed(*args):
            cls.config['DATABASE'] = TextField(_database).getText()
            print(cls.config)
            win.delete()
        _ok = button(label='ok', command=_ok_button_pressed)
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
        _proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self._stdout = _proc.communicate()[0]
        os.remove(_tempfile)
        displayInfo(self._stdout)

if __name__ == '__main__':
    try:
        CGTeamWork().show_window(True)
    except SystemExit as e:
        exit(e)
    except:
        import traceback
        traceback.print_exc()