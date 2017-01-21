# -*- coding: UTF-8 -*-

import os
import nuke
import re

def createOutDirs():
    trgDir = os.path.dirname( nuke.filename( nuke.thisNode() ) )
    if not os.path.isdir( trgDir ):
        os.makedirs( trgDir )

def convert_422HQ():
    '''
    All footage convert to mov
    Files save in system temp folder
    Mov format : 422HQ , try to maintain original fps ( default fps value: 25 )
    '''
    TEMP = os.getenv( 'TEMP' )
    r_pd = nuke.root()[ 'project_directory' ].value()
    r_prx = nuke.root()[ 'proxy' ].value()
    r_fps = nuke.root()[ 'fps' ].value()
    pd = TEMP + '\\convert_422HQ'
    nuke.root()[ 'proxy' ].setValue( 0 )
    nuke.root()[ 'project_directory' ].setValue( pd.replace( '\\', '/' ) )
    nuke.setPreset("Write", "mov_422HQ", {'mov.mov64_bitrate': '20000', 'checkHashOnRead': 'false', 'version': '3', 'file_type': 'mov', 'mov.mov64_fps': '{root.fps}', 'selected': 'true', 'mov.mov64_codec': 'apch', 'mov.meta_codec': 'apch', 'colorspace': 'sRGB', 'proxy': 'mov/proxy/[lindex [split [basename [metadata input/filename]] .] 0].mov', 'file': 'mov/[lindex [split [basename [metadata input/filename]] .] 0].mov', 'beforeRender': 'file = nuke.tcl(\'eval list {\'+nuke.thisNode()["file"].value()+\'}\');\nabsolutePath = os.path.splitdrive(file)[0];\nproject_directory = nuke.tcl(\'eval list {\'+nuke.root()["project_directory"].value()+\'}\');\npathHead = \'\' if absolutePath else project_directory+\'/\';\ntarget = pathHead+os.path.dirname(file)\nif os.path.exists(target):\n    pass;\nelse:\n    os.makedirs(target);\n', 'indicators': '2'})
    for i in nuke.allNodes():
        if i.Class() == 'Read':
            i.selectOnly()
            fps = 25
            if i.metadata( 'input/frame_rate' ) :
                fps = i.metadata( 'input/frame_rate' ) 
            nuke.root()[ 'fps' ].setValue( fps )
            w = nuke.createNode( 'Write' )
            nuke.applyPreset( '', 'mov_422HQ', w )
            nuke.render( w, int( i[ 'origfirst' ].value() ), int( i[ 'origlast' ].value() ) )
            nuke.delete( w )
    nuke.root()[ 'fps' ].setValue( r_fps )
    nuke.root()[ 'proxy' ].setValue( r_prx )
    nuke.root()[ 'project_directory' ].setValue( r_pd )
    os.system( 'EXPLORER "' + pd + '\\mov"')

def setFontsPath():
    '''
    Set Fonts path to 
    '''
    k = nuke.Root()['free_type_font_path']
    if k.value() == '':
        k.setValue( '//SERVER/scripts/NukePlugins/Fonts' )

def checkFootage( hasMsg=False ):
    '''
    If any footage exist drop frame, put it out on error console.
    @param hasMsg: Also show a dialog box. 
    '''
    if not nuke.env[ 'gui' ] :
        return 'this fucntion only work on gui mode'
    ver = '素材检查v0.1'
    s = ''
    checked = []
    for i in nuke.allNodes():
        if i.Class() == 'Read' and not i[ 'disable' ].value() :
           file = nuke.filename( i )
           if file in checked :
               continue
           checked.append( file )
           dir = os.path.dirname( file )
           file = os.path.basename( file )
           list = nuke.getFileNameList( dir, True )
           ptn = re.compile( '.*(#|%0?\d?d).*' )
           mch = ptn.match( file )
           if not mch:
               continue
           num = ptn.match( file ).group( 1 )
           ptn = file.replace( '.', '\\.' ).replace( num, '\\d*' )
           ptn = re.compile( ptn )
           for j in list :
               mch = ptn.match( j )
               if mch == None:
                   list.remove( j )
           if len( list ) > 1 :
               s += '\n' + i.name() + '\n' + str( list ) 
    if s != '':
        s = '\n    ' + ver + ':\n' + s + '\n'
        nuke.warning( s )
        if hasMsg:
            nuke.message( s )
