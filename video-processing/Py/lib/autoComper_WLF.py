#
# -*- coding=UTF-8 -*-
# WuLiFang Studio AutoComper
# Version 0.1

import nuke
import os
import re

_dict_nodeTag = {}
_dict_tagNode = {}

def main():
    # Get all footage type
    updateDict()
    
    # MergeOver
    mergeOver()
    
    # Create write node
    nuke.loadToolset("\\\\SERVER\scripts\NukePlugins\ToolSets\WLF\Write.nk")
    
    # Set framerange
    _done = False
    for i in _dict_nodeTag.keys():
        if _dict_nodeTag[i] == 'CH_A':
            nuke.Root()['first_frame'].setValue(i['first'].value())
            nuke.Root()['last_frame'].setValue(i['last'].value())
            nuke.Root()['lock_range'].setValue(True)
            _done = True
            break
    if not _done:
        nuke.message('没有找到CH_A：\n请手动设置工程帧范围')

def updateDict():
    for i in nuke.allNodes('Read'):
        tag = getFootageTag(i)
        _dict_nodeTag[i] = tag
        _dict_tagNode[tag] = i
            
    if not _dict_nodeTag:
        nuke.message('请先将素材拖入Nuke')
        return False

def getFootageTag(n):
    '''
    Figure out node footage type
    '''
    _filename = os.path.normcase(nuke.filename(n))
    _s = os.path.basename(_filename)
    _pat = re.compile(r'_sc\d+_(.*?)\.')
    result = re.search(_pat, _s)
    if result:
        result = result.group(1).upper()
    else:
        result = '_OTHER'
    return result

def getNodesByTag(tags):
    result = []    
    # Convert input param
    if type(tags) is str :
        tags = [tags]
    tags = tuple(map(str.upper, tags))
    # Output result
    for i in _dict_nodeTag.keys():
        if _dict_nodeTag[i].startswith(tags):
            result.append(i)
    return result

def mergeOver():

    # Find nodes to mergeOver
    _nodes_mergeOver = getNodesByTag(['BG', 'CH'])

    # Sort for processing order
    _order_backfront = lambda n: _dict_nodeTag[n].replace('BG', '_1_').replace('CH', '_0_')
    _nodes_mergeOver.sort(key=_order_backfront, reverse=True)
    
    # Create node
    _lastoutput = _nodes_mergeOver[0]
    for i in _nodes_mergeOver[1:]:
        _node_merge = nuke.nodes.Merge2(inputs=[_lastoutput, i])
        _lastoutput = _node_merge
    _lastoutput.selectOnly()
    placeNodes()

def mergeOCC():
    # TODO
    bg_node = getNodesByTag('BG')[0]
    for i in getNodesByTag('OCC'):
        merge_node = nuke.nodes.Merge2(inputs=[_b, i], operation='multiply')
        _lastoutput = _node_merge

    
def mergeShadow():
    # TODO
    pass

def insertNode(node, input_node):
    # Create dot presents input_node 's output
    input_node.selectOnly()
    dot = nuke.createNode('Dot')
    # Set node connection
    node.setInput(0, input_node)
    dot.setInput(0, node)
    # Delete dot
    nuke.delete(dot)
 
def placeNodes():
    # XXX
    for i in nuke.allNodes():
        i.autoplace()

def placeNode(n):
    # TODO
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

