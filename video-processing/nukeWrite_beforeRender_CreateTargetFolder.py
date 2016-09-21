file = nuke.tcl('eval list {'+nuke.thisNode()["file"].value()+'}');
absolutePath = os.path.splitdrive(file)[0];
project_directory = nuke.tcl('eval list {'+nuke.root()["project_directory"].value()+'}');
pathHead = '' if absolutePath else project_directory+'/';
target = pathHead+os.path.dirname(file)
if os.path.exists(target):
    pass;
else:
    os.makedirs(target);
