# usr/bin/env python
# -*- coding=UTF-8 -*-

import os
import shutil
from config import Config

class Sync(Config):
    def getFileList(self):
        cfg = self.config
        image_dir = cfg['IMAGE_FNAME']
        video_dir = cfg['VIDEO_FNAME']
        if os.path.exists(image_dir):
            cfg['image_list'] = list(i for i in os.listdir(image_dir) if i.endswith('.jpg'))
        else:
            cfg['image_list'] = []
        if os.path.exists(video_dir):
            cfg['video_list'] = list(i for i in os.listdir(video_dir) if i.endswith('.mov'))
        else:
            cfg['video_list'] = []

    def uploadVideo():
        if os.path.exists(os.path.dirname(video_dest)):
            if not os.path.exists(video_dest):
                os.mkdir(video_dest)
            for i in os.listdir('mov'):
                ext = os.path.splitext(i)[1].lower()
                if ext == '.mov':
                    src = 'mov\\' + i
                    dst = os.path.join(video_dest, i)
                    if os.path.exists(dst) and os.path.getmtime(src) == os.path.getmtime(dst):
                        print_('{}: 服务器文件和本地修改日期相同, 跳过'.format(src))
                        continue
                    else:
                        call(['XCOPY', '/Y', '/I', '/V', src, dst])
        else:
            print_('**错误** 视频上传文件夹不存在, 将不会上传。')

    def downloadVideo():
        pass

    def uploadImage():
        dest = self.config['image_dest']
        if os.path.exists(os.path.dirname(dest)):
            if not os.path.exists(image_dest):
                os.mkdir(image_dest)
            call(['XCOPY', '/Y', '/D', '/I', '/V', 'images\\*.jpg', dest])
        else:
            print_('**错误** 图片上传文件夹不存在, 将不会上传。')

    def downlowdImages():
        if self.config['imageDownCheck']:
            print_('下载文件自:\t\t{}'.format(self.image_download_path))
            subprocess.call(['XCOPY', '/Y', '/D', '/I', '/V', self.image_download_path, 'images'])

    def uploadCSheet():
        dest = self.config['csheet_dest']
        if self.config['csheetUpCheck']:
            if not os.path.exists(dest):
                os.mkdir(dest)
            print(u'上传文件至:\t\t{}'.format(dest))
            call(' '.join(['XCOPY', '/Y', '/D', '/I', '/V', config['csheet'], dest]))
    
    def execSyncBt(self):
        pass
