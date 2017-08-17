import relativeFilePath

workflowMenu = nuke.menu( 'Nodes' ).addMenu( 'mamoworld/Workflow', icon='MWWorkflow.png' )
nuke.menu( 'Nodes' ).addCommand( 'mamoworld/Workflow/Relative file path', 'relativeFilePath.showReplaceFilePathDialog()', icon='MWRelativeFilePath.png' )
#nuke.menu( 'Nodes' ).addCommand( 'mamoworld/Workflow/Collect files', 'nuke.message("Not yet implemented")', icon='MWCollectFiles.png' )
