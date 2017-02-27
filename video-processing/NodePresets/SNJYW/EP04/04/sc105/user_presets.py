import nuke
def nodePresetsStartup():
  nuke.setUserPreset("ColorCorrect", "SNJYW/EP04/04/sc105/Env_Dream", {'note_font': '\xe5\xbe\xae\xe8\xbd\xaf\xe9\x9b\x85\xe9\xbb\x91', 'saturation': '0.9', 'gain': '1.052840233 1.00316 1.194238067 1', 'label': "SNJYW/EP04/04/sc105/Env_Dream\n\xe9\xa2\x84\xe8\xae\xbe\xe9\x94\x81\xe5\xae\x9a :[python {nuke.applyUserPreset('', 'SNJYW/EP04/04/sc105/Env_Dream', nuke.thisNode())}]\n\n"})
