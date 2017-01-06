n = nuke.toNode('Depth3Split_Global_1');
n['size'].setValue(20);
for i in nuke.allNodes():
	if i.Class() == 'ZDefocus2':
		i['blur_dof'].setValue(False);
for i in nuke.allNodes():
    if 'ValueGamma' in i.name() and not i['disable'].value():
   	    i.showControlPanel();