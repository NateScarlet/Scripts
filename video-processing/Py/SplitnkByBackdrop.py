for i in nuke.allNodes():
    if i.Class() == 'BackdropNode':
        label = repr(i['label'].value()).strip("'").replace('\\', '_')
        filename = 'D:/splitnk/' + label + '.nk'
        i.selectOnly()
        i.selectNodes()
        nuke.nodeCopy(filename)