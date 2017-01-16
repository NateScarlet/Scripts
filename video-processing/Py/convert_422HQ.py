TEMP = os.getenv( 'TEMP' )
pd = TEMP + '\\convert_422HQ'
nuke.root()[ 'fps' ].setValue( 25 )
nuke.root()[ 'proxy' ].setValue( 0 )
nuke.root()[ 'project_directory' ].setValue( pd )
nuke.setPreset("Write", "mov_422HQ", {'mov.mov64_bitrate': '20000', 'checkHashOnRead': 'false', 'version': '3', 'file_type': 'mov', 'mov.mov64_fps': '{root.fps}', 'selected': 'true', 'mov.mov64_codec': 'apch', 'mov.meta_codec': 'apch', 'colorspace': 'sRGB', 'proxy': 'mov/proxy/[lindex [split [basename [metadata input/filename]] .] 0].mov', 'file': 'mov/[lindex [split [basename [metadata input/filename]] .] 0].mov', 'beforeRender': 'file = nuke.tcl(\'eval list {\'+nuke.thisNode()["file"].value()+\'}\');\nabsolutePath = os.path.splitdrive(file)[0];\nproject_directory = nuke.tcl(\'eval list {\'+nuke.root()["project_directory"].value()+\'}\');\npathHead = \'\' if absolutePath else project_directory+\'/\';\ntarget = pathHead+os.path.dirname(file)\nif os.path.exists(target):\n    pass;\nelse:\n    os.makedirs(target);\n', 'indicators': '2'})
for i in nuke.allNodes():
    if i.Class() == 'Read':
        i.selectOnly()
        nuke.root()[ 'first_frame' ].setValue( i[ 'origfirst' ].value() )
        nuke.root()[ 'last_frame' ].setValue( i[ 'origlast' ].value() )
        w = nuke.createNode( 'Write' )
        nuke.applyPreset( '', 'mov_422HQ', w )
        nuke.render( w )
        nuke.delete( w )
os.system( 'EXPLORER ' + pd )