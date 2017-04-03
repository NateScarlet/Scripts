# -*- coding: UTF-8 -*-

import os
import nuke
import nukescripts
import re

dropframes = {}
dropframes_showed = []

def createOutDirs():
    trgDir = os.path.dirname( nuke.filename( nuke.thisNode() ) )
    if not os.path.isdir( trgDir ):
        os.makedirs( trgDir )

def convert_422HQ():
    return 'working'
    '''
    All footage convert to mov
    Files save in system temp folder
    Mov format : 422HQ , try to maintain original fps ( default fps value: 25 )
    '''
    TEMP = os.getenv( 'TEMP' )
    nuke.root()[ 'proxy' ].setValue( 0 )
    
    # Set panel then show
    panel_text = {'output': '输出至文件夹:', 'fps': 'fps', 'force_fps': '覆盖原始fps'}
    p = nuke.Panel('convert_422HQ')
    p.addFilenameSearch(panel_text[output], TEMP)
    p.addExpressionInput(panel_text[fps], 25)
    p.show()
    output_path = p.value(panel_text[output]).rstrip('\\/') + '/convert_422HQ'
    fps = p.value(panel_text[fps])
    file = outputpath + '/mov/[lindex [split [basename [metadata input/filename]] .] 0].mov'
    
    write_node = nuke.nodes.Write(file=file, mov.mov64_codec='apch')
    nuke.setPreset("Write", "mov_422HQ", {'mov.mov64_bitrate': '20000', 'checkHashOnRead': 'false', 'version': '3', 'file_type': 'mov', 'mov.mov64_fps': '{root.fps}', 'selected': 'true', 'mov.mov64_codec': 'apch', 'mov.meta_codec': 'apch', 'colorspace': 'sRGB', 'proxy': 'mov/proxy/[lindex [split [basename [metadata input/filename]] .] 0].mov', 'file': 'mov/[lindex [split [basename [metadata input/filename]] .] 0].mov', 'beforeRender': 'file = nuke.tcl(\'eval list {\'+nuke.thisNode()["file"].value()+\'}\');\nabsolutePath = os.path.splitdrive(file)[0];\nproject_directory = nuke.tcl(\'eval list {\'+nuke.root()["project_directory"].value()+\'}\');\npathHead = \'\' if absolutePath else project_directory+\'/\';\ntarget = pathHead+os.path.dirname(file)\nif os.path.exists(target):\n    pass;\nelse:\n    os.makedirs(target);\n', 'indicators': '2'})
    for i in nuke.allNodes('Read'):
        i.selectOnly()
        if i.metadata( 'input/frame_rate' ) :
            fps = i.metadata( 'input/frame_rate' ) 
        nuke.root()[ 'fps' ].setValue( fps )
        w = nuke.nodes.Write()
        nuke.applyPreset( '', 'mov_422HQ', w )
        nuke.render( w, int( i[ 'origfirst' ].value() ), int( i[ 'origlast' ].value() ) )
        nuke.delete( w )
    cmd = 'EXPLORER "' + pd + '\\mov"'
    os.system(cmd)

def setFontsPath():
    '''
    Set Fonts path to server
    '''
    k = nuke.Root()['free_type_font_path']
    if k.value() == '':
        k.setValue( '//SERVER/scripts/NukePlugins/Fonts' )

def replaceFrame(filename, frame):
    '''
    Return a frame mark expaned version of filename, with given frame
    '''
    pat = re.compile(r'%0?\d*d')
    formated_frame = lambda matchobj: matchobj.group(0) % frame
    return re.sub(pat, formated_frame, nukescripts.frame.replaceHashes(filename))

def getDropFrameRanges( n=nuke.thisNode(), avoid=True):
    '''
    Return frameRanges of footage drop frame.
    
    @param n: node
    @param avoid: Avoid node that name endswith '_' for special use.
    @return frameranges
    '''
    # Avoid special node
    if avoid and n.name().endswith('_'):
        return None
    
    # Get dropframe ranges
    if n.Class() != 'Read' :
        return  False
    L = []
    filename = nuke.filename(n)
    for f in range( int( n['first'].value() ), int( n['last'].value() ) + 1 ):
        pth = replaceFrame(filename, f)
        if not os.path.exists( pth ):
            L.append( f )
    fgs = nuke.FrameRanges( L )
    fgs.compact()
    if not n['disable'].value() :
        dropframes[filename] = fgs
    return fgs

def showDropFrames():
    '''
    Show a dialog display all drop frames.
    '''
    if not nuke.env[ 'gui' ] :
        return 'this fucntion only work on gui mode'
    _D = dropframes
    _S = ''
    for i in _D.keys() :
        frmrgs = str(_D[i])
        if frmrgs and i not in dropframes_showed:
            dropframes_showed.append(i)
            _S += '<tr><td>' + i + '</td><td><span style=\"color:red\">' + frmrgs + '</span></td></tr>'
    if _S != '':
        _S = '<style>td{padding:8px;}</style>'\
             '<table>'\
             '<tr><th>素材</th><th>缺帧</th></tr>'\
             + _S + \
             '</table>'
        nuke.message( _S )

def allDropFrames():
    _D = dropframes
    _S = '\n'.join(_D.keys())
    return _S

def checkDropFrames():
    global dropframes
    global dropframes_showed
    dropframes = {}
    dropframes_showed = []
    for i in nuke.allNodes(group=nuke.Root()):
        getDropFrameRanges(i)
    showDropFrames()
    return
    
def DropDataCallBack_fbx(type, data):
    # Only deal with nonstyle text
    if type != 'text/plain':
        return None
    # Only deal with fbx
    if data.endswith('.fbx'):
        # Create camera node
        camera_node = nuke.nodes.Camera2(read_from_file=True, file=data, frame_rate=25, suppress_dialog=True, label='导入的摄像机：\n[basename [value file]]\n注意选择file -> node name')
        camera_node.setName('Camera_3DEnv_1')
        return True
    else:
        return None

def deleteAllUnusedNodes():
    c = 0
    done = False
    while not done:
        nodes = []
        for i in nuke.allNodes():
            if not isUsed(i):
                nodes.append(i)
                c += 1
        if nodes:
            map(lambda n: nuke.delete(n), nodes)
        else:
            done = True
    print('Deleted {} unused nodes.'.format(c))
        
def isUsed(n):
    
    if n.name().startswith('_') or n.Class() in ['BackdropNode', 'Write', 'Viewer']:
        return True
    else:
        # Deal with dependent list  
        nodes_dependent_this = filter(lambda n: n.Class() not in ['Viewer'] or n.name().startswith('_') ,n.dependent())
        return bool(nodes_dependent_this)
        
def setProjectRootByName(path='E:'):
    nuke.root()['project_directory'].setValue(os.path.dirname(path + '/' + os.path.basename(nuke.scriptName()).split('.')[0].replace('_', '/')))
    
def setWrite():
    _Write = nuke.toNode('_Write')
    if _Write:
        try:
            _Write['is_output_JPG'].setValue(False)
            _Write['isLockOnSave'].setValue(False)
            _Write['is_jump_to_frame'].setValue(False)
        except:
            nuke.error('EXCEPTION: assetManager.setWrite()')