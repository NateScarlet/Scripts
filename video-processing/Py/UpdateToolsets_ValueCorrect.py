def allKnobsName( n ):
    l1 = n.allKnobs()
    l2 = []
    for m in l1 :
        l2.append( m.name() )
    return l2

def SwapKnobValue( ka, kb ):
	va, vb = ka.value(), kb.value()
    ka.setValue( vb )
    kb.setValue( va )

for i in nuke.allNodes():
	if 'ValueCorrect' in i.name() and 'gain' in allKnobsName( i ) and 'white' in allKnobsName( i ):
        SwapKnobValue( i[ 'gain' ], i[ 'white' ] )
    if 'ValueCorrect' in i.name() or 'ValueGamma' in i.name() and 'python' not in i[ 'label' ].value() :
        i.selectOnly()
        d = os.getenv( 'UserProfile' ) + '\\.nuke\\toolsets'
        n = nuke.loadToolset( d + '\\colorcorrect\\valuecorrect.nk' )
        print( '-' * 10 + '\n' + i.name() + '\n' + '-' * 10)
        for k in i.allKnobs() :
        	kn = k.name()
        	print( kn )
        	if kn in [ 'name', '', 'label' ] :
        		pass
            elif kn == 'gain' :
            	n['white'].setValue( i[ kn ].value() )
            elif kn == 'lift' :
            	n['black'].setValue( i[ kn ].value() )
            elif kn in allKnobsName( n ) :
                n[ kn ].setValue( i[ kn ].value() )
        nuke.delete( i )