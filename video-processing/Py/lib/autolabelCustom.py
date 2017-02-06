# -*- coding=UTF-8 -*-

import nuke
from autolabel import autolabel
from assetManager import getDropFrameRanges

def autolabelCustom() :
    '''
    add addition information on Node in Gui
    '''
    a = autolabel().split( '\n' )[0]
    b = '\n'.join( autolabel().split( '\n' )[1:] )
    s = ''
    this = nuke.thisNode()
    if this.Class() == 'Keyer' :
        s = '输入通道 : ' + nuke.value( 'this.input' )
    elif this.Class() == 'Read' :
        df = str( getDropFrameRanges( this ) )
        if df :
            if not this['disable'].value():
                nuke.warning( '[缺帧]' + this.name() + ' ' + nuke.filename( this ) + ' ' + df )
            df = '\n<span style=\"color:red\">缺帧:' + df + '</span>'
        else :
            df = ''
        s = '<span style=\"color:#548DD4;font-family:微软雅黑\"><b> 帧范围 :</b></span> '\
            '<span style=\"color:red\">' + nuke.value( 'this.first' ) + ' - ' + nuke.value( 'this.last' ) + '</span>'\
             + df
    elif this.Class() == 'Shuffle' :
        ch = dict.fromkeys( [ 'in', 'in2', 'out', 'out2'], '' )
        for i in ch.keys() :
            v = nuke.value( 'this.' + i)
            if v != 'none':
                ch[ i ] = v + ' '
        s = ( ch[ 'in' ] + ch[ 'in2' ] + '-> ' + ch[ 'out' ] + ch[ 'out2' ] ).rstrip( ' ' )

    # join result
    if s :
        result = '\n'.join( [ a, s, b ] )
    elif b:
        result = '\n'.join( [ a, b ] )
    else :
        result = a
    result = result.rstrip( '\n' )
    return result