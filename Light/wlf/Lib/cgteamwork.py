# -*- coding=UTF-8 -*-

import os
import sys
import tempfile
import json
import subprocess
import locale

from pymel.all import *


VERSION = 0.141
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
    __config = dict(config)
    pref_json = os.path.join(Env.envVars['MAYA_APP_DIR'], '.wlf_cgteamwork_tool.json')
    
    def __init__(self):
        self.check_install()
        
        self.load_pref()
        
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
        cls.load_pref()

        _window_name = 'CGTeamWork'
        _all_textfiled = {}
        _labels = {
            #'SERVER': u'服务器路径', 
            'DATABASE': u'项目数据库',
            'ASSET_MODULE': u'资产模块名',
            'SHOT_TASK_MODULE': u'镜头制作模块名',
            'PIPELINE': u'环节'
        }
        if window(_window_name, exists=True):
            if refresh:
                deleteUI(_window_name)
            else:
                showWindow(_window_name)
                return True

        win = window(_window_name, sizeable=False)
        columnLayout(columnAttach=('both', 5), adjustableColumn=True)
        rowColumnLayout( numberOfColumns=2, columnAttach=(1, 'right', 1), columnWidth=[(1, 100), (2, 250)])
        for _key in _labels.keys():
            if _key in cls.config.keys():
                text(label=_labels[_key])
                _all_textfiled[_key] = textField(_key, text=cls.config[_key])
        setParent('..')
        rowLayout(numberOfColumns=2, adjustableColumn=1)
        def _ok_button_pressed(*args):
            for _key in _all_textfiled.keys():
                cls.config[_key] = TextField(_all_textfiled[_key]).getText()
            cls.save_pref()
            win.delete()
        _ok = button(label='ok', command=_ok_button_pressed)
        def _reset_button_pressed(*args):
            cls.config.update(cls.__config)
            cls.save_pref()
            win.delete()
            cls.show_window()
        _reset = button(label=u'重置', width=80, command=_reset_button_pressed)
        win.show()
        return win
        
    @classmethod
    def save_pref(cls):
        with open(cls.pref_json, 'w') as f:
            json.dump(cls.config, f, indent=4, sort_keys=True)
    
    @classmethod
    def load_pref(cls):
        if os.path.isfile(cls.pref_json):
            with open(cls.pref_json) as f:
                last_config = f.read()
            if last_config:
                cls.config.update(json.loads(last_config))

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