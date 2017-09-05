# -*- coding=UTF-8 -*-
"""license check. only intend to block non-programer user. """

import os
import sys
import pickle
import datetime

DATABASE = os.path.join(__file__, '../validation.db')


def __update_expire():
    with open(DATABASE, 'wb') as f:
        database = {'expire': datetime.date(2017, 1, 1)}
        pickle.dump(database, f)


def __is_expired():
    try:
        with open(DATABASE, 'r') as f:
            database = pickle.load(f)
            expire = database['expire']
            print(u'吾立方插件: 许可至: {}'.format(expire).encode('gbk'))
        return database['expire'] < datetime.date.today()
    except:
        return True


# __update_expire()
if __is_expired():
    import nuke
    nuke.message('吾立方插件: 许可已过期, 请联系作者获取更新许可\n要卸载请直接删除文件夹\n{}'.format(
        os.path.abspath(os.path.join(__file__, '../../'))))
    sys.exit(0)
