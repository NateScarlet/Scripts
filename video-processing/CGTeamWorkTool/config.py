#! usr/bin/env python
# -*- coding=UTF-8 -*-

import os
import sys
import json

class Config(object):
    config = {
                'SERVER': u'Z:\\CGteamwork_Test', 
                'DEST': '',
                'SHOT_PREFIX': 'SNJYW_EP14_',
                'DATABASE': 'proj_big',
                'MODULE': 'shot_task',
                'PIPELINE': u'合成',
                'video_list': [],
             }
    cfgfile_path = os.path.join(os.getenv('UserProfile'), '.CGteamworkTool.json')

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
        #print(u'设置{}: {}'.format(key, value))
        self.config[key] = value
        self.updateConfig()
