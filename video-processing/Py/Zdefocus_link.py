for i in nuke.allNodes():
    if 'ZDefocus' in i.Class() and 'Global' not in i['name'].value():
        i['size'].setExpression('ZDefocus_Global_1.size');
        i['max_size'].setExpression('ZDefocus_Global_1.max_size');
    elif  'ZDefocus' in i.Class() and 'Global' in i['name'].value():
        i['max_size'].clearAnimated();
        i['max_size'].setValue(8);