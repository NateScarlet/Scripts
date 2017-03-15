#
# -*- coding=UTF-8 -*-
# WuLiFang Studio AutoComper
# Version 0.1

import nuke
import os
import re

node_tag_dict = {}
tag_node_dict = {}
tag_convert_dict = {'BG_FOG': 'FOG_BG', 'CH_SD': 'SD_CH'}

def main():
    # Get all footage type
    updateDict()
    if not node_tag_dict:
        nuke.message('请先将素材拖入Nuke')
        return False
    print(node_tag_dict)
    
    # Merge
    n = mergeOver()
    mergeOCC()
    mergeShadow()
    mergeScreen()
    n.selectOnly()
    
    # Create write node
    nuke.loadToolset("\\\\SERVER\scripts\NukePlugins\ToolSets\WLF\Write.nk")
    
    # Place node
    placeNodes()
    
    # Set framerange
    _done = False
    for i in node_tag_dict.keys():
        if node_tag_dict[i] == 'CH_A':
            nuke.Root()['first_frame'].setValue(i['first'].value())
            nuke.Root()['last_frame'].setValue(i['last'].value())
            nuke.Root()['lock_range'].setValue(True)
            _done = True
            break
    if not _done:
        nuke.message('没有找到CH_A：\n请手动设置工程帧范围')

def updateDict():
    node_tag_dict.clear()
    tag_node_dict.clear()
    for i in nuke.allNodes('Read'):
        tag = getFootageTag(i)
        node_tag_dict[i] = tag
        tag_node_dict[tag] = i            

def getFootageTag(n):
    '''
    Figure out node footage type
    '''
    _filename = os.path.normcase(nuke.filename(n))
    _s = os.path.basename(_filename)
    _pat = re.compile(r'_sc.+?_(.*?)\.')
    result = re.search(_pat, _s)
    if result:
        result = result.group(1).upper()
        # Convert tag use dictionary
        if result in tag_convert_dict.keys():
            result = tag_convert_dict[result]
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
    for i in node_tag_dict.keys():
        if node_tag_dict[i].startswith(tags):
            result.append(i)
    return result

def mergeOver():

    # Find nodes to mergeOver
    _nodes_mergeOver = getNodesByTag(['BG', 'CH'])

    # Sort for processing order
    _order_backfront = lambda n: node_tag_dict[n].replace('BG', '_1_').replace('CH', '_0_')
    _nodes_mergeOver.sort(key=_order_backfront, reverse=True)
    
    # Create node
    if len(_nodes_mergeOver) == 0:
        return node_tag_dict.keys()[0]
    elif len(_nodes_mergeOver) == 1:
        return _nodes_mergeOver[0]
    else:
        _lastoutput = _nodes_mergeOver[0]
        for i in _nodes_mergeOver[1:]:
            _node_merge = nuke.nodes.Merge2(inputs=[_lastoutput, i], label=node_tag_dict[i])
            _lastoutput = _node_merge
        return _lastoutput

def mergeOCC():
    try:
        bg_node = getNodesByTag('BG')[0]
        for i in getNodesByTag('OCC'):
            merge_node = nuke.nodes.Merge2(inputs=[bg_node, i], operation='multiply', screen_alpha=True, label='OCC')
            insertNode(merge_node, bg_node)
    except IndexError:
        return None
        
def mergeShadow():
    try:
        bg_node = getNodesByTag('BG')[0]
        for i in getNodesByTag(['SH', 'SD']):
            grade_node = nuke.nodes.Grade(inputs=[bg_node, i], white="0.08420000225 0.1441999972 0.2041999996 0.0700000003", white_panelDropped=True, label='Shadow')
            insertNode(grade_node, bg_node)
    except IndexError:
        return None

def mergeScreen():
    try:
        bg_node = getNodesByTag('BG')[0]
        for i in getNodesByTag('FOG'):
            merge_node = nuke.nodes.Merge2(inputs=[bg_node, i], operation='screen', label=node_tag_dict[i])
            insertNode(merge_node, bg_node)
    except IndexError:
        return None
        
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

