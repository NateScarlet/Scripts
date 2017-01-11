global rsmbList;
rsmbList = [];
for i in nuke.allNodes():
    if 'rsmb' in i.Class():
        if not i['disable'].value():
            rsmbList.append(i);
            i['disable'].setValue(1);
nuke.root()['proxy'].setValue(0);
w = nuke.toNode('Write_JPG_1');
w['disable'].setValue(0);
nuke.render(w);
for i in rsmbList:
    if 'rsmb' in i.Class():
        i['disable'].setValue(0);
rsmbList = [];