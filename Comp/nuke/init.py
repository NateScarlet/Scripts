# -*- coding: UTF-8 -*-
import logging

import nuke

logging.getLogger('').setLevel(logging.DEBUG)


nuke.pluginAddPath('wlf')
nuke.pluginAddPath('cryptomatte/nuke')
nuke.pluginAddPath('mamoworld')
nuke.pluginAddPath('tabtabtab')
nuke.pluginAddPath('batchrender', addToSysPath=False)
nuke.pluginAddPath('olm_smoother')