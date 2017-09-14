# -*- coding=UTF-8 -*-
"""license check. only intend to block non-programer user. """

import os
import sys
import datetime as time

EXPIRE_AT = time.date(2018, 1, 1)

IS_EXPIRED = EXPIRE_AT < time.date.today()
print('许可至: {}'.format(EXPIRE_AT))
del EXPIRE_AT

if IS_EXPIRED:
    __import__('nuke').message('吾立方插件: 许可已过期, 请联系作者获取更新许可\n要卸载请直接删除文件夹\n{}'.format(
        os.path.abspath(os.path.join(__file__, '../../'))))
    sys.exit(0)
