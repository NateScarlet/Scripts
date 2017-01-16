import nuke

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