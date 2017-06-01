# usr/bin/env python
# -*- coding=UTF-8 -*-

import os
import json
import time

class Config(object):
    config = {
                'SERVER': r'\\192.168.1.7\z', 
                'SIMAGE_FOLDER': r'Comp\image', 
                'SVIDEO_FOLDER': r'Comp\mov', 
                'NUKE': r'C:\Program Files\Nuke10.0v4\Nuke10.0.exe', 
                'DIR': 'N:\\', 
                'PROJECT': 'SNJYW', 
                'EP': '', 
                'SCENE': '', 
                'CSHEET_FFNAME': 'images', 
                'CSHEET_PREFIX': 'Contactsheet', 
                'VIDEO_FNAME': 'mov', 
                'IMAGE_FNAME': 'images', 
                'isImageUp': 2, 
                'isImageDown': 2, 
                'isVideoUp': 2, 
                'isVideoDown': 0, 
                'isCSheetUp': 0, 
                'isCSheetOpen': 2, 
                'csheet': ''
             }
    cfgfile_path = os.path.join(os.getenv('UserProfile'), 'SceneTools_WLF.json')

    def __init__(self):
        self.readConfig()            
        self.updateConfig()
            
    def updateConfig(self):
        self.setSyncPath()
        self.setCSheetPath()
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

    def setSyncPath(self):
        cfg = self.config
        cfg['csheet_dest'] = os.path.join(cfg['SERVER'], cfg['PROJECT'], cfg['SIMAGE_FOLDER'], time.strftime('%m%d'))
        cfg['image_dest'] = os.path.join(cfg['SERVER'], cfg['PROJECT'], cfg['SIMAGE_FOLDER'], cfg['EP'], cfg['SCENE'])
        cfg['video_dest'] = os.path.join(cfg['SERVER'], cfg['PROJECT'], cfg['SVIDEO_FOLDER'], cfg['EP'], cfg['SCENE'])

    def setCSheetPath(self):
        cfg = self.config

        cfg['csheet_name'] = cfg['CSHEET_PREFIX'] + ('_{}_{}.jpg'.format(cfg['EP'], cfg['SCENE']) if cfg['EP'] and cfg['SCENE'] else '_{}.jpg'.format(time.strftime('%y%m%d_%H%M')))
        cfg['csheet'] = os.path.join(cfg['DIR'], cfg['csheet_name'])
        cfg['csheet_dest'] = os.path.join(cfg['SERVER'], cfg['PROJECT'], cfg['SIMAGE_FOLDER'], time.strftime('%m%d'))
        cfg['csheet_footagedir'] = os.path.join(cfg['DIR'], cfg['CSHEET_FFNAME'])
