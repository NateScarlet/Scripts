# -*- coding: UTF-8 -*-

import sys
import os.path
import nuke
import comp

menubar = nuke.menu( "Nuke" )
m = menubar.addMenu( u"合成".encode( 'utf8' ) )
m.addCommand( u"重命名全部节点".encode( 'utf8' ), "comp.RenameAll()" )
n = m.addMenu( u"显示面板".encode( 'utf8' ) )
n.addCommand( "ValueCorrect" , "comp.Show( 'ValueCorrect' )", 'F4' )
