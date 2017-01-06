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