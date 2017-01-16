# -*- coding: UTF-8 -*-

import sys
import os.path
import nuke
import comp

menubar = nuke.menu( "Nuke" )
m = menubar.addMenu( "合成" )
m.addCommand( "重命名全部节点", "comp.RenameAll()" )
n = m.addMenu( "显示面板" )
n.addCommand( "ValueCorrect" , "comp.Show( 'ValueCorrect' )", 'F4' )
n = m.addMenu( "工具集更新" )
n.addCommand( "ValueCorrect" , "comp.UpdateToolsets( 'ValueCorrect', r'C:\Users\zhouxuan.WLF\.nuke\ToolSets\ColorCorrect\ValueCorrect.nk' )" )
n.addCommand( "DepthFix" , "comp.UpdateToolsets( 'DepthFix', r'C:\Users\zhouxuan.WLF\.nuke\ToolSets\Depth\DepthFix.nk' )" )