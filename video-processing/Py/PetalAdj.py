n = nuke.toNode('Depth3Split_Global_1');
n['size'].setValue(20);
if not nuke.toNode('ValueGamma_Petal_1'):
	n = nuke.toNode('ValueGamma6');
	n.setName('ValueGamma_Petal_1');
n = nuke.toNode('ValueGamma_Petal_1');
nuke.applyUserPreset('', '', n);
for i in nuke.allNodes():
	if 'Write' in i['label'].value() and i.Class() == 'BackdropNode':
		f = nuke.toNode('setRootFormat_HD1080_fps25_1');
		fi = f.input(0);
		fi.selectOnly();
		XYpos0 = [fi.xpos(), fi.ypos() - 200];
		nuke.zoom(1, XYpos0);
		list0 = i.getNodes();
		for j in list0:
			nuke.delete(j);
		nuke.delete(i);
	    nuke.loadToolset(r"D:\Users\zhouxuan.WLF\CloudSync\Scripts\video-processing\ToolSets\Write.nk");
for i in nuke.allNodes():
	if i.Class() == 'Zdefocus':
		i['blur_dof'].setValue(True);