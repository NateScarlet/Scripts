# usr/bin/env python
# -*- coding=UTF-8 -*-
# Version 0.31

from PIL import Image, ImageStat, ImageOps, ImageFile
import os, sys
import statistics
import colorsys
from shutil import move, copy2
from subprocess import call
import zipfile
import io
import datetime

prompt_codec = 'GBK'
nconvert = r'C:\Program Files\nconvert.exe'
autocrop = os.path.join(os.path.dirname(__file__), '智能裁边.exe')
filtering = os.path.join(os.path.dirname(__file__), '黑白图修图(无视RGB模式图像).exe')
createzip = os.path.join(os.path.dirname(__file__), '压缩修图文件夹.bat')
ImageFile.LOAD_TRUNCATED_IMAGES = True

class CommandLineUI(object):

    working_dir = None
    joint_images = []

    def __init__(self):
        self.getDir()
        os.chdir(self.working_dir)

    def getDir(self):
        try:
            self.working_dir = sys.argv[1]
        except IndexError:
            self.working_dir = input('素材目录: ').strip('"')
    
    def showInfo(self):
        print('dir:\t{}'.format(self.working_dir))
    
    def askImageJoint(self):
        while True:
            user_input = input('需要合页拼图的图像中编号较低的那张:')
            if user_input:
                try:
                    imageR = int(user_input)
                    imageL = imageR + 1
                    print('左: {}, 右: {}'.format(imageL, imageR))
                    self.joint_images.append((imageL, imageR))
                except ValueError:
                    print('**错误** 输入内容应该为索引数字')
            else:
                break
        print(self.joint_images)
    
        
    def pause(self):
        call('PAUSE', shell=True)
        
        

class MangaProcessing(CommandLineUI):

    def __init__(self):
        super(MangaProcessing, self).__init__()
        self.image_list = {}
        self.getImageList()
        
        if not os.path.exists('raw'):
            os.mkdir('raw')

    def __call__(self):
        self.backupRaw()
        self.showOption()
        
    def showOption(self):
        try:
            while True:
                print('\n'
                      '建议先用Camera Raw自动旋转\n'
                      '1.重命名转换格式拼图\n'
                      '2.智能裁剪自动对比度\n'
                      '3.过滤镜\n'
                      '4.压缩为zip\n\n'
                      'CTRL+C 退出\n')
                choice = call('CHOICE /C 1234 /M "选择方案"', shell=True)
                if choice == 1:
                    self.backupVersion()
                    self.renameImages()
                    self.askImageJoint()
                    self.convertToPNG()
                    self.jointImage()
                    self.desarturationGreyImages()
                    print('现在应去手动调整合页拼图的位置(不补中缝)')
                elif choice == 2:
                    self.backupVersion()
                    self.smartcrop()
                    self.autocontrastImages()
                    print('现在应去手动补中缝去广告调色阶')
                elif choice == 3:
                    self.backupVersion
                    self.filtering()
                elif choice == 4:
                    self.backupVersion
                    self.createZip()
        except KeyboardInterrupt:
            exit()

    def createZip(self):
        dir_basename = os.path.basename(self.working_dir)
        with zipfile.ZipFile('{}.zip'.format('[修图]' + dir_basename), 'w') as zip_file:
            for i in self.image_list:
                zip_file.write(i, arcname=os.path.join(dir_basename, i))
            info = '修图:Nate Scarlet 邮箱：NateScarlet@Gmail.com\n'\
                   '\t\t非工作日乐意承接任何无偿漫画修图 通常于收到24小时内完成\n'\
                   '\t\t\t\t\t\t\t\t{time}'.format(time=datetime.datetime.now().strftime('%x %X'))
            zip_file.writestr(os.path.join(dir_basename, '修图 Nate.txt'), info)

    def smartcrop(self):
        for image in self.image_list:
            print('{}: 智能裁剪'.format(image))
            call('"{}" "{}"'.format(autocrop, os.path.abspath(image)))

    def getWhitepoint(self):
        pass

    def resize(self):
        pass

    def grade(self):
        pass
    
    def filtering(self):
        for image in self.image_list:
            print('{}: 过滤镜'.format(image))
            call('"{}" "{}"'.format(filtering, os.path.abspath(image)))
    
    def convertToPNG(self):
        print('## 转为PNG格式')
        try:
            call('"{}" -out png -D {}'.format(nconvert, ' '.join(self.image_list)))
            self.image_list = list(map(lambda file_name: os.path.splitext(file_name)[0] + '.png', self.image_list)) 
            print('使用nconvert转换了全部文件')
        except FileNotFoundError:
            print('推荐下载nconvert放在C:\Program Files中\n脚本自带转换不稳定')
            for index, image in enumerate(self.image_list):
                with Image.open(image) as image_object:
                    new_name = os.path.splitext(image)[0] + '.png'
                    image_object.save(new_name)
                os.remove(image)
                self.image_list[index] = new_name
                print('{} -> {}'.format(image, new_name))

    def backupRaw(self):
        for image in self.image_list:
            src = image
            dst = os.path.join('raw', image)
            if not os.path.exists(dst):
                copy2(src, dst)
    
    def backupVersion(self):
        version = 1
        while True:
            dst_folder = 'v{:02d}'.format(version)
            if not os.path.exists(dst_folder):
                os.mkdir(dst_folder)
                break
            version += 1
        for image in self.image_list:
            src = image
            dst = os.path.join(dst_folder, image)
            copy2(src, dst)

    def jointImage(self):
        print('## 合页拼图')
        gap = 100
        for (imageL, imageR) in self.joint_images:
            imageL, imageR = imageL - 1, imageR -1
            imageL_file, imageR_file = self.image_list[imageL], self.image_list[imageR]
            print('{} {}: 合并...'.format(imageL_file, imageR_file))
            with Image.open(imageL_file) as imageL_object:
                with Image.open(imageR_file) as imageR_object:
                    sizeL = imageL_object.size
                    sizeR = imageR_object.size
                    modeL = imageL_object.mode
                    modeR = imageR_object.mode

                    new_size = (sizeL[0] + sizeR[0] + gap, max(sizeL[1], sizeR[1]) + gap * 2)
                    if modeL == modeR == 'L':
                        new_mode = 'L'
                        bg_color = 255
                    else:
                        new_mode = 'RGB'
                        bg_color = (255, 255, 255)
                    new_image = Image.new(mode=new_mode, size=new_size, color=bg_color)

                    avoid_smartcrop = lambda value : 254 if value == 255 else value
                    new_image.paste(Image.eval(imageL_object, avoid_smartcrop), box = (0, gap))
                    new_image.paste(Image.eval(imageR_object, avoid_smartcrop), box = (sizeL[0] + gap, gap))

                    new_name = '{:02d}-{:02d}{}'.format(imageR + 1, imageL + 1, os.path.splitext(imageL_file)[1])
                    new_image.save(new_name)

            self.image_list[imageL] = new_name
            self.image_list[imageR] = None
            os.remove(imageL_file)
            os.remove(imageR_file)
        self.image_list = list(filter(lambda i: i, self.image_list))

    def getSartuation(self, image):
        
        with Image.open(image) as image_object:
            mode = image_object.mode
            if mode != 'RGB':
                return 0
            stat = ImageStat.Stat(image_object)
            saturation = colorsys.rgb_to_hsv(stat.mean[0], stat.mean[1], stat.mean[2])[1]
        return saturation

    def getImageList(self, dir=None):
        self.image_list = list(i for i in os.listdir() if os.path.isfile(i) and any(format for format in ['.jpg', '.png'] if i.lower().endswith(format)))
        return self.image_list
    
    def renameImages(self):
        print('## 重命名文件')
        for index, value in enumerate(self.image_list):
            new_name = '_{}'.format(value)
            os.rename(value, new_name)
            self.image_list[index] = new_name

        for index, value in enumerate(self.image_list):
            new_name = '{:02d}{}'.format(index + 1, os.path.splitext(value)[1])
            os.rename(value, new_name)
            print('{} -> {}'.format(value[1:], new_name))
            self.image_list[index] = new_name
        return self.image_list
    
    def desarturationGreyImages(self):
        print('## 自动转灰度模式')
        for image in self.image_list:
            if self.getSartuation(image) < 0.05:
                print('{}: 转为灰度模式'.format(image))
                with Image.open(image) as image_object:
                    image_object = image_object.convert("L")
                    image_object.save(image)


    def autocontrastImages(self):
        print('## 自动对比度')
        for image in self.image_list:
            with Image.open(image) as image_object:
                image_object = ImageOps.autocontrast(image_object, cutoff=10)
                image_object.save(image)
            print('{}: 自动对比度...'.format(image))

if __name__ == '__main__':
    MangaProcessing()()