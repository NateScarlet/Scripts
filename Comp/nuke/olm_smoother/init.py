# -*- coding: UTF-8 -*-
"""OLMSmoother initiate.  """
import sys
import os
import nuke

NUKE_VERSION = nuke.env['NukeVersionMajor'] + \
    nuke.env['NukeVersionMinor'] / 10.0


def _folder():
    paths = {
        'win32': 'Plugins/Win/',
        'cygwin': 'Plugins/Win/',
        'linux': 'Plugins/Linux/',
        'darwin': 'Plugins/Mac/'
    }
    path = os.path.join(os.path.dirname(__file__), paths.get(sys.platform, ''))
    versions = os.listdir(path)
    version = versions[0]
    for i in versions:
        try:
            if float(version) < float(i) <= NUKE_VERSION:
                version = i
        except ValueError:
            continue
    return os.path.join(path, version)


nuke.pluginAddPath(_folder())
