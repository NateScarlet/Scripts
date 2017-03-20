#
# -*- coding=UTF-8 -*-
# WuLiFang Studio AutoComper
# Version 0.722

import nuke
import os
import re
import sys

tag_convert_dict = {'BG_FOG': 'FOG_BG', 'BG_ID':'ID_BG', 'CH_SD': 'SH_CH', 'CH_SH': 'SH_CH', 'CH_OC': 'OCC_CH', 'CH_A_SH': 'SH_CH_A', 'CH_B_SH': 'SH_CH_B', 'CH_B_OC': 'OCC_CH_B'}

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
        if nuke.env['gui']:
            nuke.connectViewer(1, self.last_output)
        
        # Set framerange
        try:
            self.setFrameRangeByNode(self.getNodesByTag(['CH', 'BG'])[-1])
        except IndexError:
            nuke.message('没有找到CH或BG\n请手动设置工程帧范围')
        
        # Set project
        nuke.Root()['project_directory'].setValue('[python {nuke.script_directory()}]')

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
            softclip_node = nuke.nodes.SoftClip(conversion=3)
            self.insertNode(softclip_node, i)
        if len(self.bg_ch_nodes) == 1:
            self.last_output = softclip_node

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
        autoplaceAllNodes()


class precomp(comp):
    shot_pat = re.compile(r'^.+\\.+_sc[^_]+$', flags=re.I)
    footage_pat = re.compile(r'^.+_sc.+_.+\..+$', flags=re.I)

    footage_filter = lambda self, s: not any(map(lambda excluded_word: excluded_word in s, ['副本', '.lock']))
    
    def __init__(self, dir_, target_dir):

        self.dir = ''
        self.target_dir = ''
        self.shot_list = [] # Contain shot dir
        self.footage_dict = {}
        
        if nuke.env['gui']:
            precompDialog()
            return
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

    def main(self):
        error_list = []
        shots_number = len(self.shot_list)
        print('All Shot:\n{0}\nNumber of shot:\t{1}'.format('\n'.join(self.shot_list), shots_number))
        os.system('PAUSE')
        count = 0
        for shot_dir in self.shot_list:
            shot = os.path.basename(shot_dir)
            nuke.scriptClear()
            count += 1
            print('\n[{1}/{2}]Doing:\t{0}\n'.format(shot, count, shots_number))
            self.importFootage(shot_dir)
            try:
                comp()
            except:
                error_list.append(shot)
                print('**Error**\tCan not comp:\t{}'.format(shot))
            nk_filename = (self.target_dir + '/' + shot + '.nk').replace('\\', '/')
            print('Save to:\t{}'.format(nk_filename))
            nuke.Root()['name'].setValue(nk_filename)
            nuke.scriptSave(nk_filename)
            # Render Single Frame
            try:
                write_node = nuke.toNode('_Write')
                if write_node:
                    write_node = write_node.node('Write_JPG_1')
                    write_node['disable'].setValue(False)
                    frame = int(nuke.numvalue('_Write.knob.frame'))
                    nuke.execute(write_node, frame, frame)
            except:
                import traceback
                traceback.print_exc()
        info = '\nError list:\n{}\nNumber of error:\t{}'.format('\n'.join(error_list), len(error_list))
        print(info)
        os.system('PAUSE')
            
    def importFootage(self, shot_dir):
        # Get all subdir
        dirs = [x[0] for x in os.walk(shot_dir)]
        for d in dirs:
            # Get footage in subdir
            footages = nuke.getFileNameList(d)
            footages = filter(self.footage_filter, footages)
            if footages:
                # Filtring
                footages = filter(lambda path: re.match(self.footage_pat, path), footages)
                # Create read node for every footage
                for f in footages:
                    nuke.createNode( 'Read', "file {" + d + '/' + f + "}") 
        

def addMenu():
    m = nuke.menu("Nodes")
    m = m.addMenu('自动合成', icon='autoComper_WLF.png')
    m.addCommand('自动合成',"autoComper_WLF.comp()",icon='autoComper_WLF.png')
    m.addCommand('批量合成',"autoComper_WLF.precompDialog()",icon='autoComper_WLF.png')

def precompDialog():
    # Set panel 
    p = nuke.Panel('Precomp')
    p.addFilenameSearch('存放素材的文件夹', 'Z:\SNJYW\Render\EP')
    p.addFilenameSearch('存放至', 'E:\precomp')

    # Show panel
    p.show()
    cmd = 'START "precomp" "' + nuke.env['ExecutablePath'] + '" -t "' + os.path.normcase(__file__).rstrip('c') + '" "' + p.value('存放素材的文件夹') + '" "' + p.value('存放至') + '"'
    print(cmd)
    if os.path.exists(p.value('存放素材的文件夹')):
        os.popen(cmd)
    else:
        nuke.message('素材路径不存在')

def autoplaceAllNodes():
    label_ = '''[
python [python {nuke.thisNode()['_script'].value()}]
delete this
return ""
]'''
    k = nuke.PyScript_Knob('_script', '_script', 'map(lambda n: nuke.autoplace(n), nuke.allNodes(group=nuke.Root()))')
    nuke.nodes.NoOp(label=label_).addKnob(k)

# Deal call with argv

if len(sys.argv) == 3 and __name__ == '__main__':
    print('-Run precomp-')
    argv = list(map(lambda s: os.path.normcase(s).rstrip('\\'), sys.argv))
    print('Footage:\t{}\nSave to:\t{}'.format(argv[1], argv[2]))
    if not os.path.exists(argv[2]):
        os.makedirs(argv[2])
        print('Created:\t{}'.format(argv[2]))
    os.system('PAUSE')
    precomp(argv[1], argv[2])
    os.system( 'EXPLORER "' + argv[2] + '"')
