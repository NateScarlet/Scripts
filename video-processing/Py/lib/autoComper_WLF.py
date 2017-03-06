import re

nodeFootageType = {}

def getFootageType(n):
    '''
    Figure out node footage type
    '''

    _filename = nuke.filename(n)
    _s = os.path.basename(_filename)
    _pat = re.compile(r'_sc\d+_(.*?)\.')
    result = re.search(_pat, _s).group(1)
    return result

def main():
    # Get all footage type
    for i in nuke.allNodes():
        if i.Class() == 'Read':
            type = getFootageType(i)
            nodeFootageType[i] = type
    # Simple merge
    _nodes_simpleMerge = []
    for i in nodeFootageType.keys():
        if nodeFootageType[i] in ['BG_A', 'CH_A', 'CH_B', 'CH_C', 'CH_D']:
            _nodes_simpleMerge.append(i)
    # Sort for processing order
    _order_backfront = lambda n: nodeFootageType[n].replace('BG', '_1_').replace('CH', '_0_')
    _nodes_simpleMerge.sort(key=_order_backfront, reverse=True)
    
    # Create node
    for i in _nodes_simpleMerge:
        if _nodes_simpleMerge.index(i) == 0:
            _lastoutput = i
            continue
        _node_merge = nuke.nodes.Merge()
        _node_merge.setInput(0, _lastoutput)
        _node_merge.setInput(1, i)
        _lastoutput = _node_merge
        
    # Place node

        


def placeNode(n):
    inputNum = n.inputs()
    def _setNodeXY(n):
        n.setXYpos(xpos, ypos)
        nuke.autoplaceSnap(n)

    
    if inputNum == 0 or n.Class() == 'Dot':
        return False
    input0 = n.input(0)
    xpos = input0.xpos()
    ypos = input0.ypos()
    print n.name() + str(xpos)+',' + str(ypos)
    ypos += 200
    if inputNum == 1:
        n.setXYpos(xpos, ypos)
        nuke.autoplaceSnap(n)
    elif inputNum == 2:
        n.setXYpos(xpos, ypos)

        if n.input(1).Class() == 'Dot':\
            dot = n.input(1)

        else:
            dot = nuke.nodes.Dot()
            dot.setInput(0, n.input(1))
            n.setInput(1, dot)
            xpos += 100
            _setNodeXY(dot)
        xpos -= 50
        ypos -= 200
        input1 = n.input(1).input(0)
        _setNodeXY(input1)
        
main()

for i in nuke.allNodes():
    placeNode(i)
