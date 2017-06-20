# -*- coding: UTF-8 -*-

import os
import colorsys
import random

import nuke

VERSION = 1.0

def add_menu(menu=None):
    if not menu:
        menubar = nuke.menu( "Nuke" )
        m = menubar.addMenu( "合成" )
    else:
        m = menu
    m.addCommand( "重命名全部节点", "comp.RenameAll()" )
    m.addCommand( "根据Backdrop分割nk文件", "comp.splitByBackdrop()" )
    m.addCommand( "关联ZDefocus", "comp.linkZDefocus()" )
    n = m.addMenu( "显示面板" )
    m.addCommand( "修正错误的读取节点" , "comp.fix_error_read()", 'F1')
    m.addCommand( "MaskShuffle" , "comp.MaskShuffle()", 'F2' )
    n = m.addMenu( "工具集更新" )
    n.addCommand( "DepthFix" , "comp.UpdateToolsets( 'DepthFix', r'C:\Users\zhouxuan.WLF\.nuke\ToolSets\Depth\DepthFix.nk' )" )

addMenu = add_menu

def allKnobsName( n ):
    l1 = n.allKnobs()
    l2 = []
    for m in l1 :
        l2.append( m.name() )
    return l2

def RenameAll():
    for i in nuke.allNodes():
        if i.Class() == 'BackdropNode':
            if i['label'].value() == 'MP_SNJYW_EP05_01_sc063 v2.2':
                i['label'].setValue('MP v2.2\nSNJYW_EP05_01_sc063');
            list0 = i.getNodes();
            j = i['label'].value().split('\n')[0].split(' ')[0];
            for k in list0:
                if k.Class() == 'Group' and not '_' in k.name() and not (k['disable'].value()):
                    m = k.name().rstrip('0123456789');
                    k.setName(m + '_' + j + '_1', updateExpressions=True);
                elif  not '_' in k.name() and (not nuke.exists(k.name() + '.disable') or not (k['disable'].value())):
                    k.setName(k.Class() + '_' + j + '_1', updateExpressions=True);

def SwapKnobValue( ka, kb ):
    va, vb = ka.value(), kb.value()
    ka.setValue( vb )
    kb.setValue( va )

def Show( s ):
    def nodeName( n ) :
        return n.name()
    list1 = []
    for i in nuke.allNodes():
        a = 0
        try:
            a = not i['disable'].value()
        except:
            pass
        if s in i.name() and a:
            list1.append( i )
    list1.sort( key=nodeName, reverse=True )
    for i in list1:
        i.showControlPanel()
        
def UpdateToolsets( s , path ):
    for i in nuke.allNodes():
       if s in i.name() and 'python' not in i[ 'label' ].value() :
           i.selectOnly()
           n = nuke.loadToolset( path )
           for k in i.allKnobs() :
               kn = k.name()
               if kn in [ 'name', '', 'label' ] :
                   pass
               elif kn in allKnobsName( n ) :
                   n[ kn ].setValue( i[ kn ].value() )
           nuke.delete( i )

def MaskShuffle(prefix='PuzzleMatte', n=''):

    # Defaut node value, not use function default feature becuse may not selecting a node.
    if not n:
        n = nuke.selectedNode()

    # Record viewer status
    n_vw = nuke.activeViewer()
    _raw = dict.fromkeys(['has_viewer', 'viewer_input', 'viewer_channels'])
    _raw_viewer = {}
    if n_vw:
        n_vwn = n_vw.node()
        _raw['has_viewer'] = True
        _raw['viewer_input'] = n_vwn.input(0)
        if not _raw['viewer_input']:
            n_vwn.setInput(0, n)
        for knob in n_vwn.knobs():
            _raw_viewer[knob] = n_vwn[knob].value()
    else:
        _raw['has_viewer'] = False
        n_vwn = nuke.createNode('Viewer')
        n_vwn.setInput(0, n)

    # Set viewer
    nuke.activeViewer().activateInput(0)
    n_lcs = nuke.nodes.LayerContactSheet(showLayerNames=1)
    n_lcs.setInput(0, n)
    n_vwn.setInput(0, n_lcs)
    n_vwn['channels'].setValue('rgba')

    # Prepare dictionary
    _D = {}
    for i in n.channels():
        if i.startswith(prefix):
            _D[i] = ''
    _L = _D.keys()

    # Sort object on rgba order
    rgbaOrder = lambda s: s.replace(prefix + '.', '!.').replace('.red', '.0_').replace('.green', '.1_').replace('.blue', '.2_').replace('.alpha', '.3_')
    _L.sort(key=rgbaOrder)

    # Set text style
    textStyle = lambda s: s.replace('.red', '.<span style=\"color:#FF4444\">red</span>').replace('.green', '.<span style=\"color:#44FF44\">green</span>').replace('.blue', '.<span style=\"color:#4444FF\">blue</span>')
    _L_stylized = map(textStyle, _L)

    # Set panel from dictionary
    p = nuke.Panel('MaskShuffle')
    for i in range(len(_L)):
        p.addSingleLineInput(_L_stylized[i], _D[_L[i]])

    # Show panel
    p.show()
    nuke.delete(n_lcs)

    # Recover Viewer Status
    if _raw['has_viewer']:
        n_vwn.setInput(0, _raw['viewer_input'])
        for knob in n_vwn.knobs():
            try:
                n_vwn[knob].setValue(_raw_viewer[knob])
            except:
                pass
    else:
        nuke.delete(n_vwn)
    n.selectOnly()

    # Create copy
    for i in range(len(_L)):
        # Create copy node every 4 channels
        count = i % 4
        if count == 0:
            c = nuke.createNode('Copy')
            # Set two input to same node
            if c.input(1):
                c.setInput(0, c.input(1))
            elif c.input(0):
                c.setInput(1, c.input(0))
        # Prepare 'to' channel name
        _input = p.value(_L_stylized[i])
        if _input:
            to = 'mask_extra.' + _input.replace(' ', '_').replace('.', '_')
            nuke.Layer('mask_extra', [to])
        else:
            to = 'none'
        # Set node
        c['from' + str(count)].setValue(_L[i])
        c['to' + str(count)].setValue(to)
        # Delete empty copy node
        if count == 3:
            if  c['to0'].value() == c['to1'].value() == c['to2'].value() == c['to3'].value() == 'none':
                c.input(0).selectOnly()
                nuke.delete(c)

def splitByBackdrop():
    text_saveto = '保存至:'
    text_ask_if_create_new_folder = '目标文件夹不存在, 是否创建?'
    
    # Panel
    p = nuke.Panel('splitByBackdrop')
    p.addFilenameSearch(text_saveto, os.getenv('TEMP'))
    p.show()
    
    # Save splited .nk file
    save_path = p.value(text_saveto).rstrip('\\/')
    noname_count = 0
    for i in nuke.allNodes('BackdropNode'):
        label = repr(i['label'].value()).strip("'").replace('\\', '_').replace('/', '_')
        if not label:
            noname_count += 1
            label = 'noname_{0:03d}'.format(noname_count)
        if not os.path.exists(save_path):
            if not nuke.ask(text_ask_if_create_new_folder):
                return False
        dir_ = save_path + '/splitnk/'
        dir_ = os.path.normcase(dir_)
        if not os.path.exists(dir_):
            os.makedirs(dir_)
        filename = dir_ + label + '.nk'
        i.selectOnly()
        i.selectNodes()
        nuke.nodeCopy(filename)
    os.system('explorer "' + dir_ + '"')   
    return True

def linkZDefocus():
    _ZDefocus = nuke.toNode('_ZDefocus')
    if not _ZDefocus:
        return False
    for i in nuke.allNodes('ZDefocus2'):
        if not i.name().startswith('_'):
            i[ 'size' ].setExpression( '_ZDefocus.size' )
            i[ 'max_size' ].setExpression( '_ZDefocus.max_size' )
            i[ 'disable' ].setExpression( '( [ exists _ZDefocus ] ) ? !_ZDefocus.disable : 0')
            i[ 'center' ].setExpression( '( [exists _ZDefocus] ) ? _ZDefocus.center : 0' )
            i[ 'dof' ].setExpression( '( [exists _ZDefocus] ) ? _ZDefocus.dof : 0' )
            i[ 'label' ].setValue( '[\n'
                                   'set trg parent._ZDefocus\n'
                                   'if { [ exists $trg ] } {\n'
                                   '    knob this.math [value $trg.math]\n'
                                   '    knob this.z_channel [value $trg.z_channel]\n'
                                   '}\n'
                                   ']' )
    return True


def getMinMax( srcNode, channel='depth.Z' ):
    '''
    Return the min and max values of a given node's image as a tuple
    args:
       srcNode  - node to analyse
       channels  - channels to analyse. This can either be a channel or layer name
    '''
    MinColor = nuke.nodes.MinColor( channels=channel, target=0, inputs=[srcNode] )
    Inv = nuke.nodes.Invert( channels=channel, inputs=[srcNode])
    MaxColor = nuke.nodes.MinColor( channels=channel, target=0, inputs=[Inv] )
    
    curFrame = nuke.frame()
    nuke.execute( MinColor, curFrame, curFrame )
    minV = -MinColor['pixeldelta'].value()
    
    nuke.execute( MaxColor, curFrame, curFrame )
    maxV = MaxColor['pixeldelta'].value() + 1
    
    for n in ( MinColor, MaxColor, Inv ):
        nuke.delete( n )
    return minV, maxV
    
def randomGlColor(n):
    if 'gl_color' in list(i.name() for i in n.allKnobs()) and not n['gl_color'].value() and not n.name().startswith('_'):
        color = colorsys.hsv_to_rgb(random.random(), 0.8, 1)
        color = tuple(hex(int(i * 255))[2:] for i in color)
        n['gl_color'].setValue(eval('0x{}{}{}{}'.format(color[0],color[1],color[2],'00')))
    else:
        return False
        
def enableRSMB(prefix='_'):
    for i in nuke.allNodes('OFXcom.revisionfx.rsmb_v3'):
        if i.name().startswith(prefix):
            i['disable'].setValue(False)


def fix_error_read():
    while True:
        _created_node = []
        for i in filter(lambda x : x.hasError(), nuke.allNodes('Read')):
            _filename = nuke.filename(i)
            if os.path.basename(_filename).lower() == 'thumbs.db':
                nuke.delete(i)
            if os.path.isdir(_filename):
                _filename_list = nuke.getFileNameList(_filename)
                for file in _filename_list:
                    _read = nuke.createNode('Read', 'file "{}"'.format('/'.join([_filename, file])))
                    _created_node.append(_read)
                nuke.delete(i)
        if not _created_node:
            break