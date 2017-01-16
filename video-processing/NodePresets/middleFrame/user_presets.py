import nuke
def nodePresetsStartup():
  nuke.setUserPreset("ModifyMetaData", "middleFrame\", {'selected': 'true', 'note_font': '\xe5\xbe\xae\xe8\xbd\xaf\xe9\x9b\x85\xe9\xbb\x91', 'metadata': '{set comp/middleFrame "\\[expr int( ( \\[value input.first] + \\[value input.last] ) / 2 ) ]"}'})
