# usr/bin/env python
# -*- coding=UTF-8 -*-
import os
import json

class Config(object):
    config = {'NUKE': r'C:\Program Files\Nuke10.0v4\Nuke10.0.exe', 'SERVER': r'\\192.168.1.7\z', 'PROJECT': 'SNJYW', 'IMAGE_FOLDER': r'Comp\image', 'VIDEO_FOLDER': r'Comp\mov', 'EP': None, 'SCENE': None, 'isImageUp': 2, 'isImageDown': 2, 'isVideoUp': 2, 'isVideoDown': 0, 'isCsheetUp': 2}
    cfgfile_path = os.path.join(os.path.dirname(__file__), 'SceneTools.json')

    def __init__(self):
        self.readConfig()            
        self.updateConfig()
            
    def updateConfig(self):
        with open(self.cfgfile_path, 'w') as file:
            json.dump(self.config, file, indent=4, sort_keys=True)
    
    def readConfig(self):
        if os.path.exists(self.cfgfile_path):
            with open(self.cfgfile_path) as file:
                last_config = file.read()
            if last_config:
                self.config.update(json.loads(last_config))

    def editConfig(self, key, value):
        print(u'设置{}: {}'.format(key, value))
        self.config[key] = value
        self.updateConfig()
