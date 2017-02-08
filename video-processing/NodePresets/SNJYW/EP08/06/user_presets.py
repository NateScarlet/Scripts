import nuke
def nodePresetsStartup():
  nuke.setUserPreset("ColorCorrect", "SNJYW/EP08/06/Env", {'saturation': '0.95', 'note_font': '\xe5\xbe\xae\xe8\xbd\xaf\xe9\x9b\x85\xe9\xbb\x91', 'gain': '1 0.9634647965 0.9106916189 1', 'label': "SNJYW/EP08/06/Env\n\xe9\xa2\x84\xe8\xae\xbe\xe9\x94\x81\xe5\xae\x9a :[python {nuke.applyUserPreset('', 'SNJYW/EP08/06/Env', nuke.thisNode())}]\n"})
