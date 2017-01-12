# -*- coding=UTF-8 -*-

import os
import nuke
import re

def createOutDirs():
    trgDir = os.path.dirname( nuke.filename( nuke.thisNode() ) )
    if not os.path.isdir( trgDir ):
        os.makedirs( trgDir )
        
def fileFrameRange( filePath ) :
    re.complie( '.*(#.|%0\d?d).*' )

def checkFootage():
    for i in nuke.allNodes():
        if i.Class() == 'Read':
            print( i.name() )
            print( nuke.getFileNameList( os.path.dirname( nuke.filename( i ) )  )  )