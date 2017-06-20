# -*- coding: UTF-8 -*-

import os
import re
import locale
from subprocess import call

import nuke
import nukescripts

dropframes = {}
dropframes_showed = []
script_codec = 'UTF-8'
nuke_codec = 'UTF-8'
sys_codec = locale.getdefaultlocale()[1]
VESION = 1.01

class DropFrameCheck(object):
    dropframes_dict = {}
    dropframes_showed = []

    def __call__(self, ):
        self.dropframes_showed = []
        for node in nuke.allNodes(group=nuke.Root()):
            self.getDropFrameRanges(node)
        self.show()
        
    def getDropFrameRanges(self, n=nuke.thisNode(), avoid=True):
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

        dropframe_list = []
        filename = nuke.filename(n)
        first = int(n['first'].value())
        last = int(n['last'].value())
        for frame in range(first, last + 1):
            filepath = self.getFileAtFrame(filename, frame)
            if not os.path.exists(filepath):
                dropframe_list.append(frame)
        
        frameranges = nuke.FrameRanges(dropframe_list)
        frameranges.compact()
        
        try:
            n['dropframes'].setValue(str(frameranges))
        except NameError:
            k = nuke.Text_Knob('dropframes', 'dropframes', str(frameranges))
            k.setFlag(nuke.INVISIBLE)
            n.addKnob(k)

        if not n['disable'].value() :
            self.dropframes_dict[filename] = frameranges

        return frameranges
        
    def getFileAtFrame(self, filename, frame):
        '''
        Return a frame mark expaned version of filename, with given frame
        '''
        pat = re.compile(r'%0?\d*d')
        formated_frame = lambda matchobj: matchobj.group(0) % frame
        return re.sub(pat, formated_frame, nukescripts.frame.replaceHashes(filename))

    def show(self, ):
        '''
        Show a dialog display all drop frames.
        '''
        if not nuke.env[ 'gui' ] :
            raise RuntimeWarning('this fucntion only work on gui mode')
        
        message_str = ''
        for file in self.dropframes_dict.keys() :
            frameranges = str(self.dropframes_dict[file])
            if frameranges and file not in self.dropframes_showed:
                self.dropframes_showed.append(file)
                message_str += '<tr><td>{}</td><td><span style=\"color:red\">{}</span></td></tr>'.format(file, frameranges)
        if message_str != '':
            message_str = '<style>td{padding:8px;}</style>'\
                          '<table>'\
                          '<tr><th>素材</th><th>缺帧</th></tr>'\
                          + message_str + \
                          '</table>'
            nuke.message(message_str)
        
    def addCallBack(self):
        nuke.addOnCreate(lambda : self.getDropFrameRanges(nuke.thisNode()), nodeClass='Read')
        nuke.addOnScriptSave(self.show)
        
    def addMenu(self, menu=None):
        if not nuke.env['gui']:
            return False
        if not menu:
            menu = nuke.menu('Nuke').addMenu("检查缺帧")
        menu.addCommand("检查缺帧", "assetManager.DropFrameCheck()()")

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
    
    # write_node = nuke.nodes.Write(file=file, mov.mov64_codec='apch')
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
    
def addDropDataCallBack():
    DropDataCallBack.add()
    
class DropDataCallBack(object):
    @staticmethod
    def add():
        nukescripts.addDropDataCallback(DropDataCallBack.fbx)
        nukescripts.addDropDataCallback(DropDataCallBack.vf)
        nukescripts.addDropDataCallback(DropDataCallBack.db)

    @staticmethod
    def db(type, data):
        if type == 'text/plain' and os.path.basename(data).lower() == 'thumbs.db':
            return True
        else:
            return None

    @staticmethod
    def fbx(type, data):
        if type == 'text/plain' and data.endswith('.fbx'):
            camera_node = nuke.createNode('Camera2', 'read_from_file True file {data} frame_rate 25 suppress_dialog True label {{导入的摄像机：\n[basename [value file]]\n注意选择file -> node name}}'.format(data=data))
            camera_node.setName('Camera_3DEnv_1')
            return True
        else:
            return None

    @staticmethod
    def vf(type, data):
        if type == 'text/plain' and data.endswith('.vf'):
            vectorfield_node = nuke.createNode('Vectorfield', 'vfield_file "{data}" file_type vf label {{[value this.vfield_file]}}'.format(data=data))
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
    
    if n.name().startswith('_') or n.Class() in ['BackdropNode', 'Write', 'Viewer', 'GenerateLUT']:
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

def replaceSequence():
    '''
    Replace all read node to specified frame range sequence.
    '''
    # Prepare Panel
    p = nuke.Panel('单帧替换为序列')
    render_path_text = '限定只替换此文件夹中的读取节点'
    p.addFilenameSearch(render_path_text, 'z:/SNJYW/Render/')
    first_text = '设置工程起始帧'
    p.addExpressionInput(first_text, int(nuke.Root()['first_frame'].value()))
    last_text = '设置工程结束帧'
    p.addExpressionInput(last_text, int(nuke.Root()['last_frame'].value()))

    ok = p.show()
    if ok:
        render_path = p.value(render_path_text)

        first = int(p.value(first_text))
        last = int(p.value(last_text))
        flag_frame = None

        nuke.Root()['proxy'].setValue(False)
        nuke.Root()['first_frame'].setValue(first)
        nuke.Root()['last_frame'].setValue(last)

        for i in nuke.allNodes('Read'):
            file_path = nuke.filename(i)
            if file_path.startswith(render_path):
                search_result = re.search(r'\.([\d]+)\.', file_path)
                if search_result:
                    flag_frame = search_result.group(1)
                file_path = re.sub(r'\.([\d#]+)\.', lambda matchobj: r'.%0{}d.'.format(len(matchobj.group(1))), file_path)
                i['file'].setValue(file_path)
                i['format'].setValue('HD_1080')
                i['first'].setValue(first)
                i['origfirst'].setValue(first)
                i['last'].setValue(last)
                i['origlast'].setValue(last)

        _Write = nuke.toNode('_Write')
        if _Write:
            if flag_frame:
                flag_frame = int(flag_frame)
                _Write['custom_frame'].setValue(flag_frame)
                nuke.frame(flag_frame)
            _Write['use_custom_frame'].setValue(True)

def sentToRenderDir():
    if nuke.Root().modified() or not nuke.Root()['name'].value():
        return False

    if os.getenv('TEMP_RENDER'):
        src = '"{}"'.format(os.path.normcase(nuke.scriptName()))
        dst = '"{}\\"'.format(os.getenv('TEMP_RENDER').strip('"').rstrip('/\\'))
        cmd = ' '.join(['XCOPY', '/Y', '/D', '/I', '/V', src, dst])
        print(repr(cmd))
        call(cmd)
    else:
        return False

def createContactsheet():
    if nuke.Root().modified():
        return False

    bat_file =  os.path.join(os.path.dirname(nuke.scriptName()), '拼色板.py.bat'.decode('UTF-8').encode('gbk'))
    if os.path.exists(bat_file):
        call([bat_file, '4'])
    else:
        return False