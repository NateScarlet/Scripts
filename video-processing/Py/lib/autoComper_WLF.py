#
# -*- coding=UTF-8 -*-
# WuLiFang Studio AutoComper
# Version 0.4

import nuke
import os
import re

tag_convert_dict = {'BG_FOG': 'FOG_BG', 'BG_ID':'ID_BG', 'CH_SD': 'SH_CH', 'CH_SH': 'SH_CH', 'CH_OC': 'OCC_CH', 'CH_B_SH': 'SH_CH_B', 'CH_B_OC': 'OCC_CH_B'}

toolset = r'\\\\SERVER\scripts\NukePlugins\ToolSets\WLF'

class comp(object):

    order = lambda self, n: ('_' + self.node_tag_dict[n]).replace('_BG', '1_').replace('_CH', '0_')
    
    def __init__(self):

        self.node_tag_dict = {}
        self.tag_node_dict = {}
        self.bg_node = None
        self.bg_ch_nodes = []
        self.last_output = None
        for i in nuke.allNodes('Read'):
            tag = self.getFootageTag(i)
            self.node_tag_dict[i] = tag
            self.tag_node_dict[tag] = i            
        try:
            self.bg_node = self.getNodesByTag('BG')[0]
        except IndexError:
            self.bg_node = None
        self.bg_ch_nodes = self.getNodesByTag(['BG', 'CH'])
        if self.bg_ch_nodes:
            self.last_output = self.bg_ch_nodes[0]
        else:
            self.last_output = self.node_tag_dict.keys(0)
        
        if not self.node_tag_dict:
            nuke.message('请先将素材拖入Nuke')
            return False
        self.main()
    
    def main(self):
        # Merge
        self.mergeOver()
        self.addSoftClip()
        self.mergeOCC()
        self.mergeShadow()
        self.mergeScreen()
        self.mergeDepth()
        self.addZDefocus()
        
        # Create write node
        self.last_output.selectOnly()
        nuke.loadToolset(toolset + r"\Write.nk")
        
        # Place node
        self.placeNodes()
        
        # Connect viewer
        #nuke.connectViewer(1, self.last_output)
        
        # Set framerange
        try:
            self.setFrameRangeByNode(self.getNodesByTag(['CH', 'BG'])[-1])
        except IndexError:
            nuke.message('没有找到CH或BG\n请手动设置工程帧范围')

    def getFootageTag(self, n):
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

    def getNodesByTag(self, tags):
        result = []    
        # Convert input param
        if type(tags) is str :
            tags = [tags]
        tags = tuple(map(str.upper, tags))
        # Output result
        for i in self.node_tag_dict.keys():
            if self.node_tag_dict[i].startswith(tags):
                result.append(i)
        result.sort(key=self.order, reverse=True)
        return result

    def setFrameRangeByNode(self, n):
        nuke.Root()['first_frame'].setValue(n['first'].value())
        nuke.Root()['last_frame'].setValue(n['last'].value())
        nuke.Root()['lock_range'].setValue(True)
                    
    def mergeOver(self):
        if len(self.bg_ch_nodes) <= 1:
            return False
        for i in self.bg_ch_nodes[1:]:
            if not self.last_output:
                continue
            merge_node = nuke.nodes.Merge2(inputs=[self.last_output, i], label=self.node_tag_dict[i])
            self.last_output = merge_node

    def addSoftClip(self):
        for i in self.bg_ch_nodes:
            self.insertNode(nuke.nodes.SoftClip(conversion=3), i)

    def mergeOCC(self):
        try:
            merge_node = None
            for i in self.getNodesByTag('OC'):
                merge_node = nuke.nodes.Merge2(inputs=[self.bg_node, i], operation='multiply', screen_alpha=True, label='OCC')
                self.insertNode(merge_node, self.bg_node)
            return merge_node
        except IndexError:
            return False
            
    def mergeShadow(self):
        try:
            for i in self.getNodesByTag(['SH', 'SD']):
                grade_node = nuke.nodes.Grade(inputs=[self.bg_node, i], white="0.08420000225 0.1441999972 0.2041999996 0.0700000003", white_panelDropped=True, label='Shadow')
                self.insertNode(grade_node, self.bg_node)
        except IndexError:
            return False

    def mergeScreen(self):
        try:
            for i in self.getNodesByTag('FOG'):
                merge_node = nuke.nodes.Merge2(inputs=[self.bg_node, i], operation='screen', label=self.node_tag_dict[i])
                self.insertNode(merge_node, self.bg_node)
        except IndexError:
            return False

    def mergeDepth(self):
        nodes = self.bg_ch_nodes
        if len(nodes) == 1:
            return
        merge_node = nuke.nodes.Merge2(inputs=nodes[:2] + [None] + nodes[2:], operation='min', Achannels='depth', Bchannels='depth', output='depth', label='Depth')
        for i in nodes:
            depthfix_node = nuke.loadToolset(toolset + r'\Depth\Depthfix.nk')
            self.insertNode(depthfix_node, i)
        copy_node = nuke.nodes.Copy(inputs=[self.last_output, merge_node], from0='depth.Z', to0='depth.Z')
        self.insertNode(copy_node, self.last_output)
        self.last_output = copy_node
        return copy_node

    def addZDefocus(self):
        zdefocus_node = nuke.nodes.ZDefocus2(inputs=[self.last_output], math='depth', center=0.00234567, blur_dof=False, disable=True)
        zdefocus_node.setName('_ZDefocus')
        self.last_output = zdefocus_node
        return zdefocus_node

    def mergeMP(self):
        # TODO
        pass
        
    def insertNode(self, node, input_node):
        # Create dot presents input_node 's output
        input_node.selectOnly()
        dot = nuke.createNode('Dot')
        # Set node connection
        node.setInput(0, input_node)
        dot.setInput(0, node)
        # Delete dot
        nuke.delete(dot)
     
    def placeNodes(self):
        # XXX
        for i in nuke.allNodes():
            i.autoplace()


class precomp(comp):
    shot_pat = re.compile(r'^.+\\.+_sc[^_]+$', flags=re.I)
    footage_pat = re.compile(r'^.+_sc.+_.+\..+$', flags=re.I)
    
    dir = ''
    target_dir = ''
    shot_list = [] # Contain shot dir
    footage_dict = {}
    
    def __init__(self, dir_, target_dir):

        self.dir = dir_
        self.target_dir = target_dir

        # Get shot list
        if re.match(self.shot_pat, self.dir):
            self.shot_list = [self.dir]
        else:
            dirs = [self.dir + '\\' + x for x in os.listdir(self.dir)]
            dirs = filter(lambda dir : re.match(self.shot_pat, dir), dirs)
            self.shot_list = dirs

        self.main()
    
    def importFootage(self, shot_dir):
        # Get all subdir
        dirs = [x[0] for x in os.walk(shot_dir)]
        for d in dirs:
            # Get footage in subdir
            footages = nuke.getFileNameList(d)
            if footages:
                # Filtring
                footages = filter(lambda path: re.match(self.footage_pat, path), footages)
                # Create read node for every footage
                for f in footages:
                    nuke.createNode( 'Read', "file {" + d + '/' + f + "}") 

    def main(self):
        print('All Shot: {}'.format(self.shot_list))
        for shot_dir in self.shot_list:
            shot = os.path.basename(shot_dir)
            nuke.scriptClear()
            print('Doing : {}'.format(shot))
            self.importFootage(shot_dir)
            try:
                comp()
            except:
                print('Error: {}'.format(shot))
            nk_filename = (self.target_dir + '/' + shot + '.nk').replace('\\', '/')
            print('Save to :{}'.format(nk_filename))
            nuke.scriptSave(nk_filename)
            
def placeNode(n):
    # TODO
    return 
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

