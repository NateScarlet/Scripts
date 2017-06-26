# -*- coding: UTF-8 -*-
import nuke

import wlf

nuke.pluginAddPath('plugins\icons')

wlf.ui.add_menu()
wlf.pref.add_preferences()
nuke.addAutolabel(wlf.ui.custom_autolabel)
