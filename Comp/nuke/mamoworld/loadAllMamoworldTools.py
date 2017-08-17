import os
import nuke

def getFolderOfThisFile():
    """ return the folder where this module is located"""
    
    folderWithFileName = __file__
    if(folderWithFileName[-1]=='c'):
        fileName = __name__+".pyc"
    else :
        fileName = __name__+".py"
    folderLength = len(folderWithFileName) - len(fileName)
    folderWithoutFileName = folderWithFileName[:folderLength]
    
    return folderWithoutFileName

def load():
    myFolder = getFolderOfThisFile()

    subfolderNames = [name for name in os.listdir(myFolder) 
                      if os.path.isdir(os.path.join(myFolder, name))]

    subfolderNamesSorted = sorted(subfolderNames,reverse=True)
    for folderName in subfolderNamesSorted:
        folderPath = './'+folderName
        nuke.pluginAddPath(folderPath)