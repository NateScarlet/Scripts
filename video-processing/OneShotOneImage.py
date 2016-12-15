# -*- coding: UTF-8 -*-
# 同镜中只保留最新的单帧v0.2
# 将文件夹拖到此脚本上来使用

import os;
import sys;

dir = os.path.dirname(__file__);
argv1 = sys.argv[1];
imageDir = argv1.strip('"') + '\\';

def mtime(x):
	return os.stat(imageDir + x);

list = os.listdir(imageDir);
list.sort(key=mtime, reverse=True);
listB = [];
for i in list:
    listB.append(i.split('.')[0]);
for i in range(len(list)):
	listB.pop(0);
	if list[i].split('.')[0] in listB:
		os.remove(imageDir + list[i]);
