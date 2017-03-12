# -*- coding: UTF-8 -*-
# 同镜中只保留最新的单帧v0.4
# 将文件夹拖到此脚本上来使用

import os
import sys

argv1 = sys.argv[1]
imageDir = argv1.strip('"') + '\\'

mtime = lambda x : os.stat(imageDir + x).st_mtime
getShotName = lambda file_name : file_name.split('.')[0]

filename_list = list(map(os.path.normcase, os.listdir(imageDir)))
filename_list.sort(key=mtime, reverse=False)
shotname_list = list(map(getShotName, filename_list))

for i in filename_list:
    shotname_list.pop(0)
    if getShotName(i) in shotname_list:
        os.remove(imageDir + i)
        print('Removed: ' + i)
        