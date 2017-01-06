file = nuke.tcl('subst {'+nuke.thisNode()["file"].value()+'}');
absolutePath = os.path.splitdrive(file)[0];
project_directory = nuke.tcl('subst {'+nuke.root()["project_directory"].value()+'}');
pathHead = '' if absolutePath else project_directory+'/';
target = pathHead+os.path.dirname(file);
os.path.exists(target) or os.makedirs(target);
