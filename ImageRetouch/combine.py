# -*- coding=UTF-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import argparse
import locale
import logging
import os
import sys
from pypinyin import slug

try:
    _file = __file__
    _args = sys.argv
    import nuke
except:
    raise


__version__ = '0.2.0'


def script_setup():
    nuke.scriptClear()
    nuke.Root()['first_frame'].setValue(1)
    nuke.Root()['last_frame'].setValue(1)
    nuke.Root()['project_directory'].setValue(
        '[python {nuke.script_directory()}]')


def autoplace_all():
    for n in nuke.allNodes():
        nuke.autoplace(n)


def get_files(dir_):
    ret = os.listdir(dir_)
    ret = [unicode(i, sys.getfilesystemencoding()) for i in ret]
    ret = [i for i in ret if i.lower().endswith(('.jpg', '.png'))]
    return ret


def get_tags(files):
    ret = {}
    for f in files:
        name, _ = os.path.splitext(f)
        tag = name[:-1]
        ret.setdefault(tag, [])
        ret[tag].append(f)
    return ret


def create_combine(files, tag):
    _outputs = []
    for f in files:
        _read = nuke.nodes.Read(file=f.encode('UTF-8'))
        _mirror = nuke.nodes.Mirror2(inputs=[_read])
        _crop = nuke.nodes.Crop(inputs=[_mirror],
                                )
        _trans = nuke.nodes.Transform(inputs=[_crop])
        _outputs.append(_trans)
    _merge = nuke.nodes.Merge2(inputs=_outputs)
    _crop2 = nuke.nodes.Crop(
        inputs=[_merge],
        box='{{\[python nuke.thisNode().input(0).bbox().x()]}} '
        '{{\[python nuke.thisNode().input(0).bbox().y()]}} '
        '{{\[python nuke.thisNode().input(0).bbox().w()\\ +\\ nuke.thisNode().input(0).bbox().x()]}} '
            '{{\[python nuke.thisNode().input(0).bbox().h()\\ +\\ nuke.thisNode().input(0).bbox().y()]}}',
            reformat=True
    )
    _expr = nuke.nodes.Expression(
        inputs=[_crop2], channel0='rgba', expr0='1')
    _merge2 = nuke.nodes.Merge2(inputs=[_crop2, _expr], operation='under')
    filename = '{}.jpg'.format(tag)
    e_filename = filename.encode('utf-8')
    _write = nuke.nodes.Write(
        inputs=[_merge2],
        file=e_filename,
        proxy=e_filename,
        file_type='jpeg',
        _jpeg_quality=1.0,
    )


def main():
    parser = argparse.ArgumentParser(_file)
    parser.add_argument('dir', metavar='working_dir')
    args = parser.parse_args(_args[1:])

    logging.basicConfig(level=logging.DEBUG)
    files = get_files(args.dir)
    logging.debug(files)
    tags = get_tags(files)
    logging.debug(tags)
    nuke.scriptClear()

    for tag, files in tags.items():
        script_setup()
        create_combine(files, tag)
        autoplace_all()
        filename = u'{}/{num}#{tag}.nk'.format(args.dir,
                                               tag=tag, num=len(files))
        nuke.scriptSave(slug(filename, separator='').encode('UTF-8'))


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        pass
    except:
        import traceback
        traceback.print_exc()
