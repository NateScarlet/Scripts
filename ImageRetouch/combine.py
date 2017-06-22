# -*- coding=UTF-8 -*-

import os
import locale

VERSION = 0.1
SYS_CODEC = locale.getdefaultlocale()[1]

class Combine(object):
    def __init__(self):
        nuke.scriptClear()
        os.chdir(r'E:\Porojects\handwriting\0620')
        self._files = self.get_files()
        self._tags = self.get_tags()
        self.create_all()

    def get_files(self):
        _files = os.listdir(os.getcwd())
        _files = map(lambda f : unicode(f, SYS_CODEC), _files)
        return _files

    def get_tags(self):
        _tags = {}
        for f in self._files:
            _tag, _ext = os.path.splitext(f)
            _tag = _tag[:-1]
            if _ext.lower() not in ['.jpg', '.png']:
                continue
            _tags[_tag] = _tags.get(_tag, []) + [f]
        return _tags
            
    def set_project(self):
        nuke.Root()['first_frame'].setValue(1)
        nuke.Root()['last_frame'].setValue(1)
        nuke.Root()['project_directory'].setValue('[python {nuke.script_directory()}]')
        
    def create_all(self):
        nuke.scriptClear()
        for _tag, _files in self._tags.iteritems():
            self.set_project()
            self.create_combine(_tag)
            #break
            nuke.scriptSaveAndClear(u'{num}#{tag}.nk'.format(tag=_tag, num=len(self._tags[_tag])).encode('UTF-8'))

    def create_combine(self, tag):
        _outputs = []
        for f in self._tags[tag]:
            _read = nuke.nodes.Read(file=f.encode('UTF-8'))
            _mirror = nuke.nodes.Mirror2(inputs=[_read])
            _crop = nuke.nodes.Crop(inputs=[_mirror])
            _trans = nuke.nodes.Transform(inputs=[_crop])
            _outputs.append(_trans)
        _merge = nuke.nodes.Merge2(inputs=_outputs)
        _crop2 = nuke.nodes.Crop(
            inputs=[_merge],
            box=
                '{{\[python nuke.thisNode().input(0).bbox().x()]}} '\
                '{{\[python nuke.thisNode().input(0).bbox().y()]}} '\
                '{{\[python nuke.thisNode().input(0).bbox().w()\\ +\\ nuke.thisNode().input(0).bbox().x()]}} '\
                '{{\[python nuke.thisNode().input(0).bbox().h()\\ +\\ nuke.thisNode().input(0).bbox().y()]}}',
                reformat=True
        )
        _expr = nuke.nodes.Expression(inputs=[_crop2], channel0='rgba', expr0='1')
        _merge2 = nuke.nodes.Merge2(inputs=[_crop2, _expr], operation='under')
        _write = nuke.nodes.Write(
            inputs=[_merge2], 
            file=''.join([tag, '.jpg']).encode('UTF-8'), 
            file_type='jpeg',
            _jpeg_quality=1.0,
        )
        
        self.autoplace_all()

    @staticmethod
    def autoplace_all():
        for n in nuke.allNodes():
            nuke.autoplace(n)

def main():
    Combine()
    
if __name__ == '__main__':
    try:
        main()
    except:
        import traceback
        traceback.print_exc()