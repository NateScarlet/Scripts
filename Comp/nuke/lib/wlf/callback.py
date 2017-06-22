# -*- coding: UTF-8 -*-
import os

import nuke
import nukescripts

import comp
import csheet
import asset

def add_callback():
    def cgtw():
        from . import cgtw
        def on_close_callback():
            if os.path.basename(nuke.scriptName()).startswith('SNJYW'):
                cgtw.Shot().upload_image()
        nuke.addOnScriptClose(on_close_callback)
    
    cgtw()
    
    def dropframe():
        _dropframe = asset.DropFrameCheck()
        nuke.addOnCreate(lambda : _dropframe.getDropFrameRanges(nuke.thisNode()), nodeClass='Read')
        nuke.addOnScriptSave(_dropframe.show)
    
    dropframe()
    nuke.addOnScriptSave(comp.enableRSMB, kwargs={'prefix': '_'})

    nuke.addOnScriptClose(asset.sentToRenderDir)
    nuke.addOnScriptClose(csheet.create_csheet)

    def create_out_dirs():
        trgDir = os.path.dirname( nuke.filename( nuke.thisNode() ) )
        if not os.path.isdir( trgDir ):
            os.makedirs( trgDir )

    nuke.addBeforeRender(create_out_dirs, nodeClass='Write' )

    if nuke.env['gui']:
        add_dropdata_callback()

def add_dropdata_callback():
    def db(type, data):
        if type == 'text/plain' and os.path.basename(data).lower() == 'thumbs.db':
            return True
        else:
            return None

    def fbx(type, data):
        if type == 'text/plain' and data.endswith('.fbx'):
            camera_node = nuke.createNode('Camera2', 'read_from_file True file {data} frame_rate 25 suppress_dialog True label {{导入的摄像机：\n[basename [value file]]\n注意选择file -> node name}}'.format(data=data))
            camera_node.setName('Camera_3DEnv_1')
            return True
        else:
            return None

    def vf(type, data):
        if type == 'text/plain' and data.endswith('.vf'):
            vectorfield_node = nuke.createNode('Vectorfield', 'vfield_file "{data}" file_type vf label {{[value this.vfield_file]}}'.format(data=data))
            return True
        else:
            return None

    nuke.addOnCreate(lambda : comp.randomGlColor(nuke.thisNode()))

    # Person specifield setting
    if os.getenv('COMPUTERNAME') in ['WLF175']:
        def _set_write():
            _Write = nuke.toNode('_Write')
            if _Write:
                try:
                    _Write['is_output_JPG'].setValue(False)
                    _Write['isLockOnSave'].setValue(False)
                    _Write['is_jump_to_frame'].setValue(False)
                except:
                    nuke.error('EXCEPTION: callback._set_write()')

        nuke.addOnScriptLoad(_set_write)

    nukescripts.addDropDataCallback(fbx)
    nukescripts.addDropDataCallback(vf)
    nukescripts.addDropDataCallback(db)
    # nuke.addOnScriptLoad(SNJYW.setProjectRoot)
    # nuke.addOnScriptLoad(SNJYW.setRootFormat)
