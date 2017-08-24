# -*- coding=UTF-8 -*-
"""Create statistics sheet for CGTeamWork.

>>> Database('proj_big', 'asset_task').info().write('e:/test/test.json')
"""
import os
import json
import time

try:
    import sys
    sys.path.append('//SERVER/scripts/NukePlugins/wlf/py')
    from wlf.cgtwq import CGTeamWork
    from wlf.files import get_encoded
except ImportError:
    raise

__version__ = '0.1.0'


class Database(CGTeamWork):
    """CGteamwork database. """
    artist_field = 'asset_task.artist'

    def __init__(self, database=None, module=None, since=None):
        super(Database, self).__init__()
        self.database = database or self._tw.sys().get_sys_database()
        self.module = module or self._tw.sys().get_sys_module()
        self.task_module.init_with_filter([])
        self._artists = list(i for i in self.task_module.get_distinct_with_filter(
            'asset_task.artist', []) if i)

    def info(self):
        """Return all needed info as a object. """
        ret = {}
        for artist in self.artists:
            ret[artist] = self.artist(artist)
        return Info(ret)

    @property
    def artists(self):
        """Artists in this database.  """
        return self._artists

    def artist(self, name):
        """Return artists has match @name.  """
        info = self.task_module.get_with_filter(AssetTask.fields.values(),
                                                [[self.artist_field, '=', name]])
        return Artist(info)


class Artist(object):
    """Artist on CGteamwork.  """
    _tasks = []

    def __init__(self, tasks=None):
        super(Artist, self).__init__()
        if tasks:
            self._tasks = AssetTasks(tasks)

    @property
    def tasks(self):
        """Tasks assigned to this artist. """
        return self._tasks

    @tasks.setter
    def tasks(self, value):
        self._tasks = AssetTasks(value)

    def level_count(self):
        """Return count for each level.  """
        ret = {}
        ret['finished'] = self.finished_tasks().level_count()
        ret['working'] = self.working_tasks().level_count()
        return ret

    def finished_tasks(self, since=None):
        """Return finished tasks for this artist since @since given time.  """

        if isinstance(since, (str, unicode)):
            since = time.strptime(since, AssetTask.timef)

        ret = AssetTasks(task for task in self.tasks if task.is_approved
                         and(not since or task.finish_time > since))
        return ret

    def working_tasks(self, since=None):
        """Return working tasks for this artist.  """
        ret = AssetTasks(task for task in self.tasks if not task.is_approved)
        return ret


class AssetTasks(list):
    """Multiple asset task."""

    def __init__(self, tasks):
        super(AssetTasks, self).__init__()
        for task in tasks:
            if not isinstance(task, AssetTask):
                task = AssetTask(task)
            self.append(task)

    def level_count(self):
        """Return count for each level.  """
        ret = {}
        for task in self:
            level = task.level
            if not level:
                level = u'~'
            level = level.upper()
            ret.setdefault(level, 0)
            ret[level] += 1
        return ret


class AssetTask(object):
    """A asset task. """
    fields = {'level': 'asset.define_jbg',
              'finish_time': 'asset_task.finish_time',
              'submit_time': 'asset_task.last_submit_time',
              'name': 'asset.asset_name',
              'cn_name': 'asset.cn_name',
              'status': 'asset_task.status'}
    timef = '%Y-%m-%d %H:%M:%S'

    def __init__(self, info):
        super(AssetTask, self).__init__()
        assert isinstance(info, dict), 'Expected dict, got {}'.format(info)
        self._info = info

    @property
    def level(self):
        """Return diffcult level of this task"""
        return self._info[self.fields['level']]

    @property
    def is_approved(self):
        """return if this task has been approved.  """
        return self._info[self.fields['status']] == 'Approve'

    @property
    def finish_time(self):
        """Task finish time in time struct. """
        str_time = self._info[self.fields['finish_time']]
        if str_time:
            return time.strptime(str_time, self.timef)


class Info(dict):
    """Data info for asset tasks."""
    path = None

    def __init__(self, info=None):
        if isinstance(info, dict) or not info:
            dict.__init__(self, info)
        elif isinstance(info, (str, unicode))\
                and os.path.exists(get_encoded(info)):
            with open(info) as f:
                dict.__init__(self, json.load(f))
            self.path = info
        else:
            raise ValueError('Need dict or json path to initilize.')

    def generate_page(self, path):
        """Create html page form info.  """
        # TODO
        pass

    def write(self, path=None):
        """Write this info to disk.  """
        path = path or self.path
        with open(get_encoded(path), 'w') as f:
            json.dump(self, f, cls=InfoEncoder, indent=4)


class InfoEncoder(json.JSONEncoder):
    """JSONEncoder for Info."""

    def default(self, o):
        if isinstance(o, Artist):
            ret = {}
            ret['level_count'] = o.level_count()
            return ret
        elif isinstance(o, dict):
            return dict(o)
        elif isinstance(o, list):
            return list(o)

        return json.JSONEncoder.default(self, o)
