file = nuke.tcl('eval list {'+nuke.thisNode()["file"].value()+'}');
absolutePath = os.path.splitdrive(file)[0];
project_directory = nuke.tcl('eval list {'+nuke.root()["project_directory"].value()+'}');
pathHead = '' if absolutePath else project_directory;
os.makedirs(pathHead+os.path.dirname(file));
