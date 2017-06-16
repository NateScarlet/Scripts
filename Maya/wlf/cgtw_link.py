# -*- coding=UTF-8 -*-

import os
import sys
import re
import json
import locale
import pprint
from subprocess import call

CGTW_PATH = r"C:\cgteamwork\bin\base"
sys.path.append(CGTW_PATH)
import cgtw

VERSION = 0.33
SYS_CODEC = locale.getdefaultlocale()[1]

class AssetsLink(object):
    config = {
        'SERVER': u'Z:\\CGteamwork_Test', 
        #'SHOT': 'SNJYW_EP14_07_sc207',
        'DATABASE': 'proj_big',
        'ASSET_MODULE': 'asset',
        'SHOT_TASK_MODULE': 'shot_task',
        'PIPELINE': u'Layout',
        'asset_id_list': [],
        'shot_task_id': '',
        #"NAMESPACES": [
        #    ":SNJYW_BXCHT_GJ_DongRuKou_Lo", 
        #    ":SNJYW_FangYuTing_Lo", 
        #    ":SNJYW_JiGuanMuRen_Hi", 
        #    ":SNJYW_JiGuanMuRen_Hi1"
        #],
    }

    def __init__(self, config=None):
        self._config = dict(self.config)
        self._total_assets_number = -1
        if isinstance(config, dict):
            self._config.update(config)
        #pprint.pprint(self._config)
        
        self._tw = cgtw.tw()
        self._task_shots = self._tw.task_module(self._config['DATABASE'], self._config['SHOT_TASK_MODULE'])
        self._assets = self._tw.task_module(self._config['DATABASE'], self._config['ASSET_MODULE'])
        self._link = self._tw.link(self._config['DATABASE'], self._config['SHOT_TASK_MODULE'])
        self.check_login()

        self.get_shot_task_id()
        self.get_assets()
        if not self._config['asset_id_list']:
            print(u'没能从引用获取资产ID, 改为尝试从名称空间获取'.encode(SYS_CODEC))
            self.get_assets_from_namespaces()
        print('')
        
        self.link_asset()

    def is_login(self):
        ret = self._tw.sys().get_socket_status()
        return ret

    def check_login(self):
        if not self.is_login():
            raise LoginError

    def get_shot_task_id(self):
        initiated = self._task_shots.init_with_filter([['shot_task.pipeline', '=', self._config['PIPELINE']]])
        if not initiated:
            raise IDError(self._config['DATABASE'], self._config['SHOT_TASK_MODULE'],  self._config['PIPELINE'])
            return False
        
        try:
            ret = self._task_shots.get(['shot.shot'])
            if isinstance(ret, list):
                ret = filter(lambda _dict: _dict['shot.shot'] == self._config['SHOT'], ret)[0]['id']
            else:
                return False
        except IndexError:
            raise IDError(self._config['DATABASE'], self._config['SHOT_TASK_MODULE'] ,self._config['PIPELINE'], self._config['SHOT'])

        self._config['shot_task_id'] = ret
        return ret

    def get_assets(self):
        self._total_assets_number = len(self._config['REFERENCES'])
        for i in self._config['REFERENCES']:
            _asset_name = re.sub(r'(_Lo$|_Hi$)', '', i, flags=re.I)
            _asset_name = self.convert_asset_case(_asset_name)
            initiated = self._assets.init_with_filter([['asset.asset_name', '=', _asset_name]])
            if not initiated:
                print(u'未找到资产: {} -> {}'.format(i, _asset_name).encode(SYS_CODEC))
                continue
            print(u'找到资产: {} -> {}'.format(i, _asset_name).encode(SYS_CODEC))
            self._config['asset_id_list'].append(self._assets.get(['asset.asset_name'])[0]['id'])

    def get_assets_from_namespaces(self):
        self._total_assets_number = len(self._config['NAMESPACES'])
        for i in self._config['NAMESPACES']:
            _asset_name = i.split(':')[-1]
            _asset_name = re.sub(r'(_Lo\d*$|_Hi\d*$)', '', _asset_name, flags=re.I)
            _asset_name = self.convert_asset_case(_asset_name)
            initiated = self._assets.init_with_filter([['asset.asset_name', '=', _asset_name]])
            if not initiated:
                print(u'未找到资产: {} -> {}'.format(i, _asset_name).encode(SYS_CODEC))
                continue
            print(u'找到资产: {} -> {}'.format(i, _asset_name).encode(SYS_CODEC))
            self._config['asset_id_list'].append(self._assets.get(['asset.asset_name'])[0]['id'])

    def link_asset(self):
        self._link.link_asset([self._config['shot_task_id']], self._config['asset_id_list'])
        print(u'模块 {module} 中的\n[{num}/{total}]个资产Link至镜头: {shot}'.format(
            module=self._config['ASSET_MODULE'],
            shot=self._config['SHOT'], 
            num=len(self._config['asset_id_list']), 
            total=self._total_assets_number
        ).encode(SYS_CODEC))

    def convert_asset_case(self, asset_name):
        for i in self.get_all_asset_names():
            if i.lower() == asset_name.lower():
                return i
        return asset_name
    
    def get_all_asset_names(self):
        initiated = self._assets.init_with_filter([])
        if not initiated:
            return []
        ret = map(lambda x: x['asset.asset_name'], self._assets.get(['asset.asset_name']))
        return ret

def main():
    try:
        with open(sys.argv[1], mode='r') as f:
            config = json.loads(f.read())
    except IndexError:
        config =None

    AssetsLink(config)


class IDError(Exception):
    def __init__(self, *args):
        self.message = ' -> '.join(args)

    def __str__(self):
        return u'找不到对应条目: {}'.format(self.message).encode(SYS_CODEC)


class LoginError(Exception):
    def __str__(self):
        return u'CGTeamWork服务器未连接'.encode(SYS_CODEC)


if __name__ == '__main__':
    try:
        main()
    except SystemExit as e:
        exit(e)
    except:
        import traceback
        traceback.print_exc()
        