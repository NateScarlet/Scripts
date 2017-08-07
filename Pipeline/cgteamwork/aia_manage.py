# -*- coding=UTF-8 -*-
import sys

try:
    import cgtw
except ImportError:
    sys.path.append(r"C:\cgteamwork\bin\base")
    import cgtw

AIA_ATTR = 'asset_task.define_iic'
FILE_PATH_ATTR = 'asset_task.submit_file_path'


def checkin():
    """Set file read-only and set aia status to approve the archive it.  """
    pass


def checkout():
    """Set current file writable and set aia status to waiting."""
    pass


def set_shot_aia_status(status):
    """Set aia dropdown value.  """
    pass


def archive(file_path):
    """Backup file to a folder. """
    pass


class CurrentAsset(object):
    """Current asset selected from cgtw, mayby multiple item.  """

    def __init__(self):
        self._sys = self.plugin_sys()
        self._tw = cgtw.tw()
        self._id_list = self._sys.get('id')
        self._info_module = self._tw().info_module(, self._id_list)
        self._submit_files = self._sys.get('submit_file')

    def plugin_sys(self):
        """Return current asset info.  """
        ret = {}
        id_list = self._tw().sys().get_sys_id()
        ret['id_list'] = id_list
        files = i
        pass

    @property
    def id_list(self):
        """asset id.  """
        return self._id_list

    @property
    def submit_files(self):
        """Submitted file path.  """
        return self._submit_files

    @property
    def submit_file_path(id):
        """Return submit file path from cgtw id.  """
        pass


def plugin_operation():
    """Get plugin setting from cgtw.  """

    teamwork = cgtw.tw()
    operation = teamwork.sys().get_argv_key('operation')
    if operation == 'checkin':
        checkin()
    elif operation == 'checkout':
        checkout()


if __name__ == '__main__':
    plugin_operation()
