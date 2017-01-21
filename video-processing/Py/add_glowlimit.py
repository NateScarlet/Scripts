n = nuke.toNode( 'Glow2_GlobalAdjust_1' )
n[ 'effect_only' ].setValue( True )
n[ 'mix' ].setValue( 1.0 )
n[ 'maskChannelInput' ].setValue( 'none' )
nuke.toNode( 'Depth3Split_Global_1' )[ 'size' ].value( 0 )
ni = n.input( 0 )
ni.selectOnly()
ni = nuke.createNode( 'Dot' )
nuke.autoplaceSnap( ni )
x, y = ni.xpos() + 76, ni.ypos() - 13
nuke.createNode( 'Premult', 'alpha BG_A.alpha' ).setXYpos( x, y )
y += 51
n.selectOnly()
n.setXYpos( x, y )
y += 51
mi1 = nuke.createNode( 'Premult', 'alpha BG_A.alpha' )
mi1.setXYpos( x, y )
x -= 110
y += 5
m = nuke.createNode( 'Merge2', 'operation screen maskChannelInput depth3split.Focus mix 0.38' )
m.setXYpos( x, y )
m.setInput( 1, mi1 )
m.setInput( 0, ni )