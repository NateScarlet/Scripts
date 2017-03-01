def ReplaceFileName(n, serc, repl):
    if i.Class() == 'Read':
        n['file'].setValue(n['file'].value().replace(serc, repl))
        n['proxy'].setValue(n['proxy'].value().replace(serc, repl))
        print n.name() + serc + repl

script_name = str(os.path.basename(nuke.scriptName()).split('.')[0].replace('SNJYW_', ''))
thier_footage = 'Z:/SNJYW/Light/EP06/SNJYW_EP06_COM/' + script_name + '/images'

for i in nuke.allNodes():
    ReplaceFileName(i, 'E:/jyw/comp/EP06/SNJYW_' + script_name + '/nuke/renders/xulie/images', thier_footage)
    ReplaceFileName(i, 'E:/jyw/comp/EP06/SNJYW_' + script_name + '/nuke/renders/images/images/', thier_footage)
    ReplaceFileName(i, 'E:/jyw/comp/EP06/SNJYW_' + script_name + '/nuke/renders/images', thier_footage)
    ReplaceFileName(i, 'X:/ProjectRender/JYM/SNJYW_' + script_name, thier_footage)
    
nuke.root()['project_directory'].setValue(os.path.dirname('E:/SNJYW/' + script_name.replace('_', '/')))