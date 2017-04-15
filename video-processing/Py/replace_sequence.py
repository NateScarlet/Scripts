import re
render_path = 'z:/SNJYW/Render/'

first = int(nuke.Root()['first_frame'].value())
last = int(nuke.Root()['last_frame'].value())
flag_frame = None

nuke.Root()['proxy'].setValue(False)
for i in nuke.allNodes('Read'):
    file_path = nuke.filename(i)
    if file_path.startswith(render_path):
        search_result = re.search(r'\.([\d]+)\.', file_path)
        if search_result:
            flag_frame = search_result.group(1)
        file_path = re.sub(r'\.([\d#]+)\.', lambda matchobj: r'.%0{}d.'.format(len(matchobj.group(1))), file_path)
        i['file'].setValue(file_path)
        i['format'].setValue('HD_1080')
        i['first'].setValue(first)
        i['origfirst'].setValue(first)
        i['last'].setValue(last)
        i['origlast'].setValue(last)

_Write = nuke.toNode('_Write')
if _Write:
    if flag_frame:
        flag_frame = int(flag_frame)
        _Write['custom_frame'].setValue(flag_frame)
        nuke.frame(flag_frame)
    _Write['use_custom_frame'].setValue(True)