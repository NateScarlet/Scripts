for i in nuke.allNodes():
    if 'ZDefocus' in i.Class() :
        if 'Global' not in i[ 'name' ].value():
            i[ 'size' ].setExpression( 'ZDefocus_Global_1.size' )
            i[ 'max_size' ].setExpression( 'ZDefocus_Global_1.max_size' )
            i[ 'disable' ].setExpression( '( [ exists ZDefocus_Global_1 ] ) ? !ZDefocus_Global_1.disable : 0')
            i[ 'center' ].setExpression( '( [exists ZDefocus_Global_1] ) ? ZDefocus_Global_1.center : 0' )
            i[ 'dof' ].setExpression( '( [exists ZDefocus_Global_1] ) ? ZDefocus_Global_1.dof : 0' )
            i[ 'label' ].setValue( '[\n'
                                   'set trg parent.ZDefocus_Global_1\n'
                                   'if { [ exists $trg ] } {\n'
                                   '    knob this.math [value $trg.math]\n'
                                   '    knob this.z_channel [value $trg.z_channel]\n'
                                   '}\n'
                                   ']' )
        elif 'Global' in i['name'].value() :
            # i[ 'max_size' ].clearAnimated()
            # i[ 'max_size' ].setValue(8)
            pass