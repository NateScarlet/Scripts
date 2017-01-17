import os
import nuke

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
    k = nuke.Root()['free_type_font_path']
    if k.value() == '':
        k.setValue( '//SERVER/scripts/NukePlugins/Fonts' )

def fileFrameRange( filePath ) :
    '''
    not finished
    '''
    re.complie( '.*(#.|%0\d?d).*' )

def checkFootage():
    '''
    not finished
    '''
    for i in nuke.allNodes():
        if i.Class() == 'Read':
            print( i.name() )
            print( nuke.getFileNameList( os.path.dirname( nuke.filename( i ) )  )  )
