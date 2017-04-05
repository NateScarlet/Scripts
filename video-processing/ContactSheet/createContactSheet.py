#usr/bin/env python
# -*- coding=UTF-8 -*-
# version 0.1
import os
import sys
import re
import subprocess

# Read ini for nuke path
os.chdir(os.path.dirname(__file__))
ini_file = open('path.ini', 'r')

for line in ini_file.readlines():
    result = re.match('^([^;].*)=(.*)', line)
    if result:
        var_name = result.group(1)
        var_value = result.group(2)
        locals()[var_name] = var_value
        print('{}: {}'.format(var_name, var_value))
print('')

try: 
    import nuke
except ImportError:
    if not NUKE:
        NUKE = input('请输入正确的Nuke路径')
    os.system('START "createContactSheet" {} -t {}'.format(NUKE, __file__))
    exit()

class createContactSheet(object):
    def __init__(self, image_dir='images'):
        os.system('CHCP 936&CLS')
        self.image_list=self.getImageList(image_dir)
        self.image_dir=image_dir.replace('\\', '/')
        nuke.Root()['project_directory'].setValue(os.getcwd().replace('\\', '/'))
        self.main()
        
    def main(self):
        for i in self.image_list:
            nuke.nodes.Read(file=self.image_dir + '/' + i.decode('gbk').encode('UTF-8'))
            
        nuke.scriptSave('E:\\temp.nk')
        pass
        
    def getImageList(self, dir='images'):
        file_list = map(os.path.normcase, os.listdir(dir))
        
        image_filter = lambda str: any(str.endswith(i) for i in ['.jpg', '.png', '.mov'])
        image_list = filter(image_filter, file_list)
        mtime = lambda file: os.stat(dir + '\\' + file).st_mtime
        image_list.sort(key=mtime, reverse=False)
        
        # Exclude excess image
        getShotName = lambda file_name : file_name.split('.')[0]
        shot_list = list(set(getShotName(i) for i in image_list))
        for image in image_list:
            print(image)
            shot = getShotName(image)
            if shot in shot_list:
                shot_list.remove(shot)
            else:
                image_list.remove(image)
                print('Exclude: {}'.format(image))

        return image_list

createContactSheet()

os.system('PAUSE')