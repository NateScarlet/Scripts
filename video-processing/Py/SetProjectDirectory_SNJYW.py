script_name = str(os.path.basename(nuke.scriptName()).split('.')[0].replace('SNJYW_', ''))
    
nuke.root()['project_directory'].setValue(os.path.dirname('E:/SNJYW/' + script_name.replace('_', '/')))