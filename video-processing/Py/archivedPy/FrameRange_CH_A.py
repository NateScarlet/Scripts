m = nuke.toNode( "root" );
m["first_frame"].setValue(eval('nuke.toNode("CH_A").firstFrame()'));
m["last_frame"].setValue(eval('nuke.toNode("CH_A").lastFrame()'));