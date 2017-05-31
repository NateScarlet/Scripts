# usr/bin/env python
# -*- coding=UTF-8 -*-   

import re
import os

ini_dict = dict.fromkeys(['EP', 'IMAGE_FOLDER', 'NUKE', 'PROJECT', 'SCENE', 'SERVER'])
dp0 = os.path.dirname(__file__)

def readIni(ini_file= os.path.join(dp0, 'path.ini')):
    with open(ini_file, 'r') as ini_file:
        for line in ini_file.readlines():
            result = re.match('^([^;].*)=(.*)', line)
            if result:
                var_name = result.group(1)
                var_value = result.group(2)
                ini_dict[var_name] = var_value.strip('"')
                print(var_name, var_value)