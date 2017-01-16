nuke.loadToolset( 'C:/Users/zhouxuan.WLF/.nuke/ToolSets/Cache/mask_fog.nk' )
nuke.cloneSelected()
nuke.nodeCopy( 'mask_fog' )
nuke.undo()
nuke.undo()

for i in [ 'CH_A', 'CH_B', 'CH_C', 'CH_D', 'BG_A']:
    s = ''
    n = nuke.toNode( i )
    if n == None :
       continue
    for j in nuke.allNodes() :
        if j.Class() == 'BackdropNode':
            v = j['label'].value()
            if i in v :
                s = v.split( '\n' )[ 0 ].split( ' ' )[ 0 ]
    ni = n.input( 0 )
    ni.selectOnly()
    nuke.nodePaste( 'mask_fog' )
    m = nuke.toNode( 'Merge2_' + s + '_1' )
    m.selectOnly()
    mo = nuke.createNode( 'Merge2' )
    mo.setInput( 0, m )
    mo.setInput( 1, m.input( 1 ) )
    mo.setInput( 3, m.input( 3 ) )
    nuke.applyUserPreset( '', 'mask_fog', mo )
    