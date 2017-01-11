# -*- coding=UTF-8 -*-

import os
import nuke
import re

def createOutDirs():
    trgDir = os.path.dirname( nuke.filename( nuke.thisNode() ) )
    if not os.path.isdir( trgDir ):
        os.makedirs( trgDir )
        
def fileFrameRange( filePattern, fileName ) :
    re.complie( '.*(#.|%0\d?d).*' )