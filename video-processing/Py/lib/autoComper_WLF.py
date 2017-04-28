#
# -*- coding=UTF-8 -*-
# WuLiFang Studio AutoComper
# Version 0.85

import nuke
import os
import re
import sys
import traceback
from subprocess import call
import time

fps = 25
format = 'HD_1080'
tag_convert_dict = {'BG_FOG': 'FOG_BG', 'BG_ID':'ID_BG', 'CH_ID':'ID_CH', 'CH_SD': 'SH_CH', 'CH_SH': 'SH_CH', 'CH_OC': 'OCC_CH', 'CH_AO': 'OCC_CH', 'CH_A_SH': 'SH_CH_A', 'CH_B_SH': 'SH_CH_B', 'CH_C_SH': 'SH_CH_C', 'CH_D_SH': 'SH_CH_D', 'CH_OC': 'OCC_CH', 'CH_OCC': 'OCC_CH', 'CH_A_OC': 'OCC_CH_A', 'CH_A_OCC': 'OCC_CH_A', 'CH_B_OC': 'OCC_CH_B', 'CH_B_OCC': 'OCC_CH_B', 'CH_C_OC': 'OCC_CH_C', 'CH_C_OCC': 'OCC_CH_C', 'CH_D_OC': 'OCC_CH_D', 'CH_D_OCC': 'OCC_CH_D'}
regular_tag_list = ['CH_A', 'CH_B', 'CH_C', 'CH_D', 'BG_A', 'BG_B', 'BG_C', 'BG_D', 'OCC', 'SH']
toolset = r'\\\\SERVER\scripts\NukePlugins\ToolSets\WLF'
default_mp = "Z:/SNJYW/MP/EP09/sky_01_v4.jpg"
prompt_codec = 'GBK'
script_codec = 'UTF-8'

class Comp(object):

    order = lambda self, n: ('_' + self.node_tag_dict[n]).replace('_BG', '1_').replace('_CH', '0_')
    
    def __init__(self, mp=default_mp):

        self.last_output = None
        self.node_tag_dict = {}
        self.tag_node_dict = {}
        self.bg_node = None
        self.bg_ch_nodes = []
        self.mp = mp.replace('\\', '/')
        
        # Get dict
        for i in nuke.allNodes('Read'):
            tag = self.getFootageTag(i)
            self.node_tag_dict[i] = tag
            self.tag_node_dict[tag] = i
        if not self.node_tag_dict:
            nuke.message(u'请先将素材拖入Nuke')
            raise FootageError

        # Get bg_node
        try:
            self.bg_node = self.getNodesByTag('BG')[0]
        except IndexError:
            self.bg_node = None
        
        # Get bg_ch_nodes
        self.bg_ch_nodes = self.getNodesByTag(['BG', 'CH'])
        
        # Set default last_output
        if self.bg_ch_nodes:
            self.last_output = self.bg_ch_nodes[0]
        else:
            self.last_output = self.node_tag_dict.keys()[0]
    
    def __call__(self):
        self.renameReads()
        
        # Merge
        self.mergeOver()
        self.addCrop()
        self.addZDefocus()
        self.addSoftClip()
        self.addDepthFog()
        self.mergeOCC()
        self.mergeShadow()
        self.mergeScreen()
        self.addPremult()
        self.addHueCorrect()
        self.addColorCorrect()
        self.addUnremult()
        self.addGrade()
        self.mergeDepth()
        self.addReformat()
        self.addDepth()
        self.addKeyer()
        self.add_ZDefocus()
        self.mergeMP()
        
        # Create write node
        self.last_output.selectOnly()
        _Write = nuke.loadToolset(toolset + r"\Write.nk")

        # Set framerange
        try:
            self.setFrameRangeByNode(self.getNodesByTag(['CH', 'BG'])[-1])
        except IndexError:
            nuke.message('没有找到CH或BG\n请手动设置工程帧范围')
        first, last = nuke.Root()['first_frame'].value(), nuke.Root()['last_frame'].value()
        nuke.frame((first + last) // 2.0)
        
        # Set project
        if not nuke.Root()['project_directory'].value():
            nuke.Root()['project_directory'].setValue('[python {nuke.script_directory()}]')
        nuke.Root()['fps'].setValue(fps)
        nuke.Root()['format'].setValue(format)
        
        self.connectViewer()
        
        self.autoplaceAllNodes()
        self.zoomToFitAll()

        self.showPanels()

    def connectViewer(self):
        viewer_node = nuke.toNode('Viewer1')
        if not viewer_node:
            viewer_node = nuke.nodes.Viewer()
        _Write = nuke.toNode('_Write')
        viewer_node.connectInput(0, self.last_output)
        viewer_node.connectInput(1, self.last_output)
        viewer_node.connectInput(2, self.last_output)
        if _Write:
            viewer_node.connectInput(3, _Write)
        
    def getFootageTag(self, n):
        '''
        Figure out node footage type
        '''
        # Deal with footage that have no alpha
        if not 'rgba.alpha' in n.channels():
            return '_OTHER'
            
        # Try file name
        _filename = os.path.normcase(nuke.filename(n))
        _s = os.path.basename(_filename)
        _pat = re.compile(r'_sc.+?_([^.]+)')
        result = re.search(_pat, _s)
        if result:
            result = result.group(1).upper()
            # Convert tag use dictionary
            if result in tag_convert_dict.keys():
                result = tag_convert_dict[result]
        else:
            result = '_OTHER'
        # Try folder name
        if result not in regular_tag_list:
            folder_name = os.path.basename(os.path.dirname((os.path.normcase(nuke.filename(n)))))
            dir_tag = re.search(_pat, folder_name)
            if dir_tag and dir_tag.group(1).upper() in regular_tag_list:
                result = dir_tag.group(1).upper()
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
                reformat_node = nuke.nodes.Reformat()
                for j in self.bg_ch_nodes:
                    if j == self.bg_node:
                        merge_disable = False
                    else:
                        merge_disable = True
                    merge_node = nuke.nodes.Merge2(inputs=[None, i], operation='screen', maskChannelInput='rgba.alpha', label=self.node_tag_dict[i], disable=merge_disable)
                    self.insertNode(merge_node, j)
                self.insertNode(nuke.nodes.Dot(), i)
                self.insertNode(reformat_node, i)
        except IndexError:
            return False

    def mergeDepth(self):
        nodes = self.bg_ch_nodes
        if len(nodes) == 1:
            return
        merge_node = nuke.nodes.Merge2(inputs=nodes[:2] + [None] + nodes[2:], tile_color=2184871423L, operation='min', Achannels='depth', Bchannels='depth', output='depth', label='Depth', hide_input=True)
        for i in nodes:
            print('mergeDepth():\t\t{}'.format(os.path.basename(i.metadata('input/filename'))))
            depthfix_node = nuke.loadToolset(toolset + r'\Depth\Depthfix.nk')
            if self.getMax(i, 'depth.Z') > 1.1 :
                depthfix_node['farpoint'].setValue(10000)
                print('farpoint -> 10000')
            self.insertNode(depthfix_node, i)
            print('')
        copy_node = nuke.nodes.Copy(inputs=[self.last_output, merge_node], from0='depth.Z', to0='depth.Z')
        self.insertNode(copy_node, self.last_output)
        self.last_output = copy_node
        return copy_node

    def addReformat(self):
        for i in self.bg_ch_nodes:
            reformat_node = nuke.nodes.Reformat()
            self.insertNode(reformat_node, i)
        return reformat_node
        
    def addZDefocus(self):
        for i in self.bg_ch_nodes:
            zdefocus_node = nuke.nodes.ZDefocus2(math=nuke.value('_ZDefocus.math', 'depth'), center='{{[value _ZDefocus.center curve]}}', focal_point='inf inf', dof='{{[value _ZDefocus.dof curve]}}', blur_dof='{{[value _ZDefocus.blur_dof curve]}}', size='{{[value _ZDefocus.size curve]}}', max_size='{{[value _ZDefocus.max_size curve]}}', label='[\nset trg parent._ZDefocus\nknob this.math [value $trg.math depth]\nknob this.z_channel [value $trg.z_channel depth.Z]\nif {[exists _ZDefocus]} {return "由_ZDefocus控制"} else {return "需要_ZDefocus节点"}\n]', disable='{{[if {[value _ZDefocus.focal_point "200 200"] == "200 200" || [value _ZDefocus.disable]} {return True} else {return False}]}}', selected=True )
            self.insertNode(zdefocus_node, i)
        return zdefocus_node
        
    def add_ZDefocus(self):
        # Use for one-node zdefocus control
        zdefocus_node = nuke.nodes.ZDefocus2(inputs=[self.last_output], math='depth', output='focal plane setup', center=0.00234567, blur_dof=False, label='** 虚焦总控制 **\n在此拖点定虚焦及设置')
        zdefocus_node.setName('_ZDefocus')
        return zdefocus_node
        
    def addGrade(self):
        for i in self.bg_ch_nodes:
            print('addGrade(): \t\t{}'.format(os.path.basename(i.metadata('input/filename'))))
            rgb_max = self.getMax(i, 'rgb')
            erode_size = 0
            erode_node = nuke.nodes.Dilate(inputs=[i], size = erode_size)
            grade_mix = 0.6
            # Exclude small highlight
            while rgb_max > 1 and erode_size > i.height() / -100.0:
                erode_node['size'].setValue(erode_size)
                print('erode_size = {}'.format(erode_size))
                rgb_max = self.getMax(erode_node, 'rgb')
                if rgb_max < 1:
                    if rgb_max < 0.5:
                        grade_mix = 0.3
                    break
                erode_size -= 1
            nuke.delete(erode_node)
            grade_node = nuke.nodes.Grade(whitepoint=rgb_max, unpremult='rgba.alpha', mix=grade_mix, label='最亮值: {}\n混合:[value this.mix]\n使亮度范围靠近0-1'.format(rgb_max))
            self.insertNode(grade_node, i)
            print('')
        return grade_node
        
    def addDepth(self):
        for i in self.bg_ch_nodes:
            if 'depth.Z' not in i.channels():
                print('addDepth():\t\t{}'.format(os.path.basename(i.metadata('input/filename'))))
                constant_node = nuke.nodes.Constant(channels='depth', color=1, label='**用渲染出的depth层替换这个**\n或者手动指定数值')
                merge_node = nuke.nodes.Merge2(inputs=[None, constant_node], also_merge='all', label='addDepth')
                self.insertNode(merge_node, i)

    def addColorCorrect(self):
        for i in self.bg_ch_nodes:
            if 'SSS.alpha' in i.channels():
                colorcorrect_node = nuke.nodes.ColorCorrect(label='SSS调整', maskChannelInput='SSS.alpha')
                self.insertNode(colorcorrect_node, i)
            colorcorrect_node = nuke.nodes.ColorCorrect(label='颜色调整', mix_luminance=1)
            self.insertNode(colorcorrect_node, i)
            colorcorrect_node = nuke.nodes.ColorCorrect(label='亮度调整')
            self.insertNode(colorcorrect_node, i)
        return colorcorrect_node
        
    def addHueCorrect(self):
        for i in self.bg_ch_nodes:
            huecorrect_node = nuke.nodes.HueCorrect()
            self.insertNode(huecorrect_node, i)
        return huecorrect_node
    
    def addPremult(self):
        premult_node = False
        for i in self.bg_ch_nodes:
            if 'rgba.alpha' in i.channels():
                premult_node = nuke.nodes.Premult()
                self.insertNode(premult_node, i)
        return premult_node

    def addUnremult(self):
        unpremult_node = False
        for i in self.bg_ch_nodes:
            if 'rgba.alpha' in i.channels():
                unpremult_node = nuke.nodes.Unpremult()
                self.insertNode(unpremult_node, i)
        return unpremult_node    

    def addDepthFog(self):
        node_color = 596044543

        # Add _DepthFogControl node
        _DepthFogControl = nuke.loadToolset(toolset + '/Depth/DepthKeyer.nk')
        _DepthFogControl.setInput(0, self.last_output)
        _DepthFogControl.setName('_DepthFogControl')
        _DepthFogControl['label'].setValue('**深度雾总控制**\n在此设置深度雾范围及颜色')
        _DepthFogControl['range'].setValue(1)
        _DepthFogControl['gl_color'].setValue(node_color)
        _DepthFogControl['tile_color'].setValue(node_color)
        _DepthFogControl.addKnob(nuke.Text_Knob('颜色控制'))
        _DepthFogControl.addKnob(nuke.Color_Knob('fog_color', '雾颜色'))
        _DepthFogControl['fog_color'].setValue((0.009, 0.025133, 0.045))
        k = nuke.Double_Knob('fog_mix', 'mix')
        k.setValue(1)
        _DepthFogControl.addKnob(k)
        
        # Insert depthfog nodes
        for i in self.bg_ch_nodes:
            group_node = nuke.nodes.Group(tile_color=node_color, label='深度雾\n由_DepthFogControl控制', disable='{_DepthFogControl.disable}')
            group_node.setName('DepthFog1')
            group_node.begin()

            input = nuke.nodes.Input(name='Input')

            depthkeyer_node = nuke.loadToolset(toolset + '/Depth/DepthKeyer.nk')
            depthkeyer_node.setInput(0, input)
            depthkeyer_node['range'].setExpression('_DepthFogControl.range')

            grade_node = nuke.nodes.Grade(inputs=[input, depthkeyer_node], black='{_DepthFogControl.fog_color} {_DepthFogControl.fog_color} {_DepthFogControl.fog_color}', unpremult='rgba.alpha', mix='{_DepthFogControl.fog_mix}')

            output = nuke.nodes.Output(inputs=[grade_node])

            group_node.end()

            self.insertNode(group_node, i)

    def addSoftClip(self):
        for i in self.bg_ch_nodes:
            softclip_node = nuke.nodes.SoftClip(conversion=3)
            self.insertNode(softclip_node, i)
        if len(self.bg_ch_nodes) == 1:
            self.last_output = softclip_node

    def addKeyer(self):
        keyer_node = False
        for i in self.bg_ch_nodes:
            if 'SSS.alpha' in i.channels():
                keyer_node = nuke.nodes.Keyer(input='SSS', output='SSS.alpha', operation='luminance key', range='0 0.007297795507 1 1')
                self.insertNode(keyer_node, i)
        return keyer_node

    def addCrop(self): 
        for i in self.bg_ch_nodes:
            crop_node = nuke.nodes.Crop(box='0 0 {root.width} {root.height}')
            self.insertNode(crop_node, i)
        return crop_node
        
    def addVectorField(self):
        pass
        
    def mergeMP(self):
        #TODO:add lut;crop
        read_node = nuke.nodes.Read(file=self.mp)
        read_node.setName('MP')
        merge_node = nuke.nodes.Merge(inputs=[self.last_output, read_node], operation='under', label='MP')
        self.last_output = merge_node
        
        root_width, root_height = nuke.Root().width(), nuke.Root().height()
        
        self.insertNode(nuke.nodes.Defocus(disable=True), read_node)
        self.insertNode(nuke.loadToolset(toolset + r'\MP\ProjectionMP.nk'), read_node)
        ramp_node = nuke.nodes.Ramp(p0='1700 1000', p1='1700 500')
        self.insertNode(nuke.nodes.Grade(inputs=[read_node, ramp_node]), read_node)
        self.insertNode(nuke.nodes.ColorCorrect(), read_node)
        self.insertNode(nuke.nodes.Transform(center='{} {}'.format(root_width / 2.0, root_height / 2.0), label='**在此调整MP位置**'), read_node)
        self.insertNode(nuke.nodes.Reformat(resize='fill'), read_node)
    
    def renameReads(self):
        for i in nuke.allNodes('Read'):
            if i in self.node_tag_dict:
                i.setName(self.node_tag_dict[i], updateExpressions=True)

    def showPanels(self):
        nuke.nodes.NoOp(label='[\npython {nuke.show(nuke.toNode(\'_ZDefocus\'))}\ndelete this\n]')

    def insertNode(self, node, input_node):
        # Create dot presents input_node 's output
        input_node.selectOnly()
        dot = nuke.createNode('Dot')
        
        # Set node connection
        node.setInput(0, input_node)
        dot.setInput(0, node)
        
        # Delete dot
        nuke.delete(dot)

    def autoplaceAllNodes(self):
        nuke.nodes.NoOp(label='[\npython {map(lambda n: nuke.autoplace(n), nuke.allNodes(group=nuke.Root()))}\ndelete this\n]')

    def clearNodeSelect(self):
        dot = nuke.nodes.Dot()
        dot.selectOnly()
        nuke.delete(dot)

    def zoomToFitAll(self):
        self.clearNodeSelect()
        nuke.nodes.NoOp(label='[\npython {nuke.zoomToFitSelected()}\ndelete this\n]')

    def getMax(self, n, channel='depth.Z' ):
        '''
        Return themax values of a given node's image at middle frame
        @parm n: node
        @parm channel: channel for sample
        '''
        # Get middle_frame
        middle_frame = (n.frameRange().first() + n.frameRange().last()) // 2
        
        # Create nodes
        invert_node = nuke.nodes.Invert( channels=channel, inputs=[n])
        mincolor_node = nuke.nodes.MinColor( channels=channel, target=0, inputs=[invert_node] )
        
        # Execute
        try:
            nuke.execute( mincolor_node, middle_frame, middle_frame )
            max_value = mincolor_node['pixeldelta'].value() + 1
        except RuntimeError, e:
            if 'Read error:' in str(e):
                max_value = -1
            else:
                raise RuntimeError, e
                
        # Avoid dark frame
        if max_value < 0.7:
            nuke.execute( mincolor_node, n.frameRange().last(), n.frameRange().last() )
            max_value = max(max_value, mincolor_node['pixeldelta'].value() + 1)
        if max_value < 0.7:
            nuke.execute( mincolor_node, n.frameRange().first(), n.frameRange().first() )
            max_value = max(max_value, mincolor_node['pixeldelta'].value() + 1)
            
        # Delete created nodes
        for i in ( mincolor_node, invert_node ):
            nuke.delete( i )

        # Output
        print('getMax({1}, {0}) -> {2}'.format(channel, n.name(), max_value))
        
        return max_value

class Precomp(object):
    shot_pat = re.compile(r'^.+\\.+_sc[^_]+$', flags=re.I)
    footage_pat = re.compile(r'^.+_sc.+_.+\..+$', flags=re.I)

    footage_filter = lambda self, s: not any(map(lambda excluded_word: excluded_word in s, ['副本', '.lock']))
    
    def __init__(self, dir_=None, target_dir=None, mp=default_mp, footage_pat=r'^.+_sc.+_.+\..+$', dir_pat=r'.+',):

        self.dir = ''
        self.target_dir = ''
        self.shot_list = [] # Contain shot dir
        self.footage_dict = {}
        self.mp = mp
        self.dir = dir_
        self.target_dir = target_dir
        self.footage_pat = re.compile(footage_pat, flags=re.I)
        self.dir_pat = re.compile(dir_pat, flags=re.I)

    def __call__(self):

        # Get shot list
        if re.match(self.shot_pat, self.dir):
            self.shot_list = [self.dir]
        else:
            dirs = [self.dir + '\\' + x for x in os.listdir(self.dir)]
            dirs = filter(lambda dir : re.match(self.shot_pat, dir), dirs)
            dirs.sort()
            self.shot_list = dirs


        self.shots_number = len(self.shot_list)
        print_('全部镜头:\n{0}\n总计:\t{1}'.format('\n'.join(self.shot_list), self.shots_number))
        print('')
        for i in range(5)[::-1]:
            sys.stdout.write('\r\r{:2d}'.format(i+1))
            time.sleep(1)
        sys.stdout.write('\r          ')
        
        self.compAll()
        
        cmd = 'EXPLORER /select,"{}\\批量预合成.log"'.format(argv[2].strip('"')).decode(script_codec).encode(prompt_codec)
        call(cmd)
        choice = call(u'CHOICE /t 15 /d y /m "此窗口将自动关闭"'.encode(prompt_codec))
        if choice == 2:
            call('PAUSE', shell=True)
    
    def compAll(self):  
        error_list = []

        count = 0
        for shot_dir in self.shot_list:
            shot = os.path.basename(shot_dir)
            nk_filename = (self.target_dir + '/' + shot + '.nk').replace('\\', '/')

            count += 1
            print('\n## [{1}/{2}]:\t\t{0}'.format(shot, count, self.shots_number))
            
            if os.path.exists(nk_filename):
                print_('**提示** 已存在{}, 将直接跳过\n'.format(nk_filename))
                continue

            try:
                
                # Comp
                nuke.scriptClear()
                self.importFootage(shot_dir)
                Comp(self.mp)()

                # Save nk
                print_('保存为:\n\t\t\t{}\n'.format(nk_filename))
                nuke.Root()['name'].setValue(nk_filename)
                nuke.scriptSave(nk_filename)

                # Render Single Frame
                write_node = nuke.toNode('_Write')
                if write_node:
                    write_node = write_node.node('Write_JPG_1')
                    write_node['disable'].setValue(False)
                    frame = int(nuke.numvalue('_Write.knob.frame'))
                    try:
                        nuke.execute(write_node, frame, frame)
                    except RuntimeError:
                        try: nuke.execute(write_node, write_node.firstFrame(), write_node.firstFrame())
                        except RuntimeError:
                            try:
                                nuke.execute(write_node, write_node.lastFrame(), write_node.lastFrame())
                            except RuntimeError:
                                error_list.append('{}:\t渲染出错'.format(shot))
            except FootageError:
                error_list.append('{}:\t没有素材'.format(shot))
            except:
                error_list.append('{}:\t未知错误'.format(shot))
                traceback.print_exc()
        info = '错误列表:\n{}\n总计:\t{}'.format('\n'.join(error_list), len(error_list))
        print('')
        print_(info)
        with open(str(self.target_dir+'/批量预合成.log').decode(script_codec).encode(prompt_codec), 'w') as log:
            log.write('总计镜头数量:\t{}\n'.format(self.shots_number))
            log.write(info)

    def showDialog(self):
        # Set panel 
        p = nuke.Panel('Precomp')
        p.addFilenameSearch('存放素材的文件夹', 'Z:\SNJYW\Render\EP')
        p.addFilenameSearch('存放至', 'E:\precomp')
        p.addFilenameSearch('指定MP', default_mp)
        p.addSingleLineInput('素材名正则', r'^.+_sc.+_.+\..+$')
        p.addSingleLineInput('文件夹名正则', r'^.*[^\\]{8,}$')

        # Show panel
        ok = p.show()
        if ok:
            cmd = 'START "precomp" "{nuke}" -t "{script}" "{footage_path}" "{save_path}" "{mp}" "{footage_pat}" "{dir_pat}"'.format(nuke=nuke.env['ExecutablePath'], script=os.path.normcase(__file__).rstrip('c'), footage_path=p.value('存放素材的文件夹'), save_path=p.value('存放至'), mp=p.value('指定MP'), footage_pat=p.value('素材名正则'), dir_pat=p.value('文件夹名正则'))
            print(cmd)
            if os.path.exists(p.value('存放素材的文件夹')):
                call(cmd, shell=True)
            else:
                nuke.message('素材路径不存在')
        else:
            return False

    def importFootage(self, shot_dir):
        # Get all subdir
        dirs = [x[0] for x in os.walk(shot_dir)]
        print_('导入素材:')
        for d in dirs:
            # Get footage in subdir
            print_('文件夹 {}:'.format(d))
            footages = nuke.getFileNameList(d)
            if not re.match(self.dir_pat, d):
                print_('\t\t\t不匹配文件夹正则, 跳过\n'.format(d))
                continue
            if footages:
                # Filtring
                footages = filter(self.footage_filter, footages)
                footages = filter(lambda path: re.match(self.footage_pat, path), footages)
                # Create read node for every footage
                for f in footages:
                    nuke.createNode( 'Read', "file {" + d + '/' + f + "}") 
                    print('\t' * 3 + f)
            print('')
        print('')

    def importCamera(self):
        pass
        
class FootageError(Exception):
    def __init__(self):
        print_("**错误** - 没有找到素材")
                    
def addMenu():
    m = nuke.menu("Nodes")
    m = m.addMenu('自动合成', icon='autoComper_WLF.png')
    m.addCommand('自动合成',"autoComper_WLF.Comp()()",icon='autoComper_WLF.png')
    m.addCommand('批量合成',"autoComper_WLF.Precomp().showDialog()",icon='autoComper_WLF.png')

def print_(obj):
    print(str(obj).decode(script_codec).encode(prompt_codec))

if __name__ == '__main__' and  len(sys.argv) == 6:
    argv = list(map(lambda s: os.path.normcase(s).rstrip('\\/'), sys.argv))

    call(u'CHCP 936 & TITLE 批量预合成_吾立方 & CLS'.encode(prompt_codec), shell=True)
    print_('{:-^50s}'.format('确认设置'))
    print_('素材路径:\t\t{0[1]}\n保存路径:\t\t{0[2]}\nMP:\t\t\t{0[3]}\n素材名正则匹配:\t\t{0[4]}\n文件夹名正则匹配:\t{0[5]}'.format(argv))

    if not os.path.exists(argv[2]):
        os.makedirs(argv[2])
        print('Created:\t{}'.format(argv[2]))
    print('')
    for i in range(5)[::-1]:
        sys.stdout.write('\r{:2d}'.format(i+1))
        time.sleep(1)
    sys.stdout.write('\r          ')
    print('')

    Precomp(argv[1], argv[2], argv[3], argv[4], argv[5])()
