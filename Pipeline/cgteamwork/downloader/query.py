# -*- coding=UTF-8 -*-
"""Query info from cgteamwork.  """


def get_file_list(self):
    self.check_login()
    self.config['video_list'] = []
    path_field_name = 'shot_task.submit_file_path'

    self._task_module = self._tw.task_module(
        self.config['DATABASE'], self.config['MODULE'])
    initiated = self._task_module.init_with_filter(
        [['shot_task.pipeline', '=', self.config['PIPELINE']]])
    if not initiated:
        print(u'找不到对应流程: {}'.format(self.config['PIPELINE']).encode(SYS_CODEC))
        return False

    items = self._task_module.get([path_field_name, 'shot.shot'])
    for i in items:
        if i['shot.shot'] and i['shot.shot'].startswith(self.config['SHOT_PREFIX']):
            path_field_value = i[path_field_name]
            if path_field_value:
                self.config['video_list'] += eval(path_field_value)['path']
