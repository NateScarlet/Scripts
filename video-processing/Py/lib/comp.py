# -*- coding: UTF-8 -*-

import nuke

def addMenu():
    menubar = nuke.menu( "Nuke" )
    m = menubar.addMenu( "合成" )
    m.addCommand( "重命名全部节点", "comp.RenameAll()" )
    n = m.addMenu( "显示面板" )
    n.addCommand( "ValueCorrect" , "comp.Show( 'ValueCorrect' )", 'F1' )
    m.addCommand( "MaskShuffle" , "comp.MaskShuffle()", 'F2' )
    n = m.addMenu( "工具集更新" )
    n.addCommand( "ValueCorrect" , "comp.UpdateToolsets( 'ValueCorrect', r'C:\Users\zhouxuan.WLF\.nuke\ToolSets\ColorCorrect\ValueCorrect.nk' )" )
    n.addCommand( "DepthFix" , "comp.UpdateToolsets( 'DepthFix', r'C:\Users\zhouxuan.WLF\.nuke\ToolSets\Depth\DepthFix.nk' )" )

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
                nuke.delete(c)