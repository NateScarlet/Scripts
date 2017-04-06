# usr/bin/env python
# -*- coding=UTF-8 -*-
# createContactSheet
# Version 2.0
'''
REM load py script from bat
@ECHO OFF & CLS
REM Read ini
REM Won't support same variable name in diffrent block
FOR /F "usebackq eol=; tokens=1,* delims==" %%a IN ("%~dp0path.ini") DO (
    IF NOT "%%b"=="" (
        SET "%%a=%%b"
    )
)

CALL :getPythonPath %NUKE%
START "createContactSheet" %PYTHON% %0 %*
GOTO :EOF

:getPythonPath
SET "PYTHON="%~dp1python.exe""
GOTO :EOF
'''
import os
import sys
import re
import time

# Read ini
os.chdir(os.path.dirname(__file__))
ini_file = open('path.ini', 'r')

EP = None
SCENE = None
NUKE = None

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

def print_(obj):
    print(str(obj).decode(script_codec).encode(prompt_codec))

# Main
VERSION = 2.0
prompt_codec = 'gbk'
script_codec = 'UTF-8'
os.system(u'CHCP 936 & TITLE 生成色板_v{} & CLS'.format(VERSION).encode(prompt_codec))

# Display choice
print_('方案1:\t\t\t仅渲染单帧\n'\
       '方案2:\t\t\t__不可用__\n'\
       '方案3:\t\t\t__不可用__\n')
choice = os.system(u'CHOICE /C 123 /T 15 /D 1 /M "选择方案"'.encode(prompt_codec))
if choice == 1:
    pass
else:
    exit()

class createContactSheet(object):

    last_output = None
    backdrop_read_node = None
    read_nodes = None
    shot_width, shot_height = 1920, 1080

    def __init__(self, image_dir='images'):

        self.image_list = self.getImageList(image_dir)
        self.image_dir = image_dir.replace('\\', '/')
        self.read_nodes = []
        self.jpg_output = None

        self.main()
        
        global image
        image = self.jpg_output
        
    def main(self):
        nuke.Root()['project_directory'].setValue(os.getcwd().replace('\\', '/'))

        self.createReadNodes()
        self.createContactSheet()
        self.createBackdrop('灯光合成模板_底板.jpg')
        self.mergeBackdrop()
        self.modifyShot()
        self.modifyBackdrop()
        nuke.scriptSave('E:\\temp.nk')
        self.writeJPG()
        return 

    
    def createContactSheet(self):
        contactsheet_node = nuke.nodes.ContactSheet(inputs=self.read_nodes, width='{rows*shot_format.w+gap*(rows+1)}', height='{columns*shot_format.h+gap*(columns+1)}', rows='{{ceil(pow([inputs this], 0.5))}}', columns='{rows}', gap=50, roworder='TopBottom')
        contactsheet_node.addKnob(nuke.WH_Knob('shot_format'))
        contactsheet_node['shot_format'].setValue([1920, 1160])
        contactsheet_node.setName('_ContactSheet')
        self.contactsheet_node = contactsheet_node
        return contactsheet_node
    
    def createReadNodes(self):
        for i in self.image_list:
            read_node = nuke.nodes.Read(file=self.image_dir + '/' + i)
            if read_node.hasError():
                nuke.delete(read_node)
                print_('不能读取:\t\t{}'.format(i))
            else:
                self.read_nodes.append(read_node)

    def createBackdrop(self, image='灯光合成模板_底板.jpg'):
        if os.path.exists(os.path.abspath(image.decode(script_codec).encode(prompt_codec))):
            read_node = nuke.nodes.Read(file=image)
            self.backdrop_read_node = read_node
            print_('使用背板:\t\t{}'.format(image))
            return read_node
        else:
            self.backdrop_read_node = nuke.nodes.Constant()
            print_('**提示**\t\t找不到背板文件,将用纯黑代替')
            return False

    def getImageList(self, dir='images'):
        file_list = list(i.decode(prompt_codec).encode(script_codec) for i in os.listdir(dir))
        
        image_filter = lambda str: any(str.endswith(i) for i in ['.jpg', '.png', '.mov'])
        image_list = filter(image_filter, file_list)
        mtime = lambda file: os.stat(dir + '\\' + file.decode(script_codec). encode(prompt_codec)).st_mtime
        image_list.sort(key=mtime, reverse=False)
        
        # Exclude excess image
        getShotName = lambda file_name : file_name.split('.')[0].lower()
        shot_list = list(set(getShotName(i) for i in image_list))
        for image in image_list:
            shot = getShotName(image)
            if shot in shot_list:
                shot_list.remove(shot)
                print_('包含:\t\t\t{}'.format(image))
            else:
                image_list.remove(image)
                print_('排除(较旧):\t\t{}'.format(image))
        image_list.sort()
        print_('总计有效图像数量:\t{}'.format(len(image_list)))
        return image_list
    
    def mergeBackdrop(self):
        merge_node = nuke.nodes.Merge2(inputs=[self.backdrop_read_node, self.contactsheet_node])
        _reformat_backdrop_node = nuke.nodes.Reformat(type='scale', scale='{_ContactSheet.width/input.width*backdrop_scale}')
        k = nuke.Double_Knob('backdrop_scale', '背板缩放')
        k.setValue(1.13365)
        _reformat_backdrop_node.addKnob(k)
        _reformat_backdrop_node.setName('_Reformat_Backdrop')
        insertNode(_reformat_backdrop_node, self.backdrop_read_node)
        insertNode(nuke.nodes.Transform(translate='{1250*_Reformat_Backdrop.scale} {100*_Reformat_Backdrop.scale}', center='{input.width/2} {input.height/2}'), self.contactsheet_node)
        self.last_output = merge_node
        return merge_node
        
    def modifyShot(self):
        nuke.addFormat('1920 1160 contactsheet_shot')
        for i in self.read_nodes:
            reformat_node = nuke.nodes.Reformat(format='contactsheet_shot',center=False, black_outside=True)
            transform_node = nuke.nodes.Transform(translate='0 {}'.format(1160-self.shot_height))
            text_node = nuke.nodes.Text2(message='[lrange [split [basename [metadata input/filename]] ._] 3 3]', box='0 0 0 80', color='0.145 0.15 0.14 1')
            insertNode(text_node, i)
            insertNode(transform_node, i)
            insertNode(reformat_node, i)
        
    def modifyBackdrop(self):
        nuke.addFormat('11520 6480 backdrop')
        reformat_node = nuke.nodes.Reformat(format='backdrop')
        if EP:
            if EP.startswith('EP'):
                ep = EP[2:]
            else:
                ep = EP
            insertNode(nuke.nodes.Text2(message=ep, box='288 6084 1650 6400', xjustify='center', yjustify='center', global_font_scale=3, color='0.155'), self.backdrop_read_node)
        if SCENE:
            insertNode(nuke.nodes.Text2(message=SCENE, box='288 4660 1650 5000', xjustify='center', yjustify='center', global_font_scale=3, color='0.155'), self.backdrop_read_node)
        insertNode(reformat_node, self.backdrop_read_node)
        
    def writeJPG(self):
        if EP and SCENE:
            file_name = 'ContactSheet_{}_{}.jpg'.format(EP, SCENE)
        else:
            file_name = 'ContactSheet_{}.jpg'.format(time.strftime('%y%m%d_%I%M'))
        write_node = nuke.nodes.Write(inputs=[self.last_output], file=file_name, file_type='jpg', _jpeg_quality='1', _jpeg_sub_sampling='4:4:4', )
        print_('输出色板:\t\t{}'.format(file_name))
        nuke.render(write_node, 1, 1)
        self.jpg_output = os.path.abspath(file_name)
        return file_name

def insertNode(node, input_node):
    # Create dot presents input_node 's output
    input_node.selectOnly()
    dot = nuke.createNode('Dot')
    
    # Set node connection
    node.setInput(0, input_node)
    dot.setInput(0, node)
    
    # Delete dot
    nuke.delete(dot)


try:
    createContactSheet('images')
    choice = os.system(u'CHOICE /t 15 /d n /m "打开图像"'.encode(prompt_codec))
    if choice == 1:
        os.system(u'EXPLORER "{}"'.format(image).encode(prompt_codec))
except:
    import traceback
    traceback.print_exc()
    os.system('PAUSE')
