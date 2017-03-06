import nuke
def nodePresetsStartup():
  nuke.setUserPreset("ColorCorrect", "SNJYW/EP04/04/Light_Dream", {'note_font': '\xe5\xbe\xae\xe8\xbd\xaf\xe9\x9b\x85\xe9\xbb\x91', 'gain': '1.396666646 0.9666666985 0.6366666555 1', 'label': "[python {str('SNJYW/EP04/' + os.path.splitext(os.path.basename(nuke.scriptName()))[0].split('_')[-2] + '/Light_Dream')}]\n\xe9\xa2\x84\xe8\xae\xbe\xe9\x94\x81\xe5\xae\x9a :[python {nuke.applyUserPreset('', str('SNJYW/EP04/' + os.path.splitext(os.path.basename(nuke.scriptName()))[0].split('_')[-2] + '/Light_Dream'), nuke.thisNode())}]\n"})
  nuke.setUserPreset("ColorCorrect", "SNJYW/EP04/04/Color_DreamBG", {'note_font': '\xe5\xbe\xae\xe8\xbd\xaf\xe9\x9b\x85\xe9\xbb\x91', 'gain': '0.006674752571 0.01118451729 0.01183466706 0.02999999933', 'label': "[python {str('SNJYW/EP04/' + os.path.splitext(os.path.basename(nuke.scriptName()))[0].split('_')[-2] + '/Color_DreamBG')}]\n\xe9\xa2\x84\xe8\xae\xbe\xe9\x94\x81\xe5\xae\x9a :[python {nuke.applyUserPreset('', str('SNJYW/EP04/' + os.path.splitext(os.path.basename(nuke.scriptName()))[0].split('_')[-2] + '/Color_DreamBG'), nuke.thisNode())}]\n"})
  nuke.setUserPreset("ColorCorrect", "SNJYW/EP04/04/Light_Fire", {'indicators': '2', 'saturation': '0.5', 'note_font': '\xe5\xbe\xae\xe8\xbd\xaf\xe9\x9b\x85\xe9\xbb\x91', 'gain': '1.921544671 0.9595447779 -0.678455174 1', 'label': "[python {str('SNJYW/EP04/' + os.path.splitext(os.path.basename(nuke.scriptName()))[0].split('_')[-2] + '/Light_Fire')}]\n\xe9\xa2\x84\xe8\xae\xbe\xe9\x94\x81\xe5\xae\x9a :[python {nuke.applyUserPreset('', str('SNJYW/EP04/' + os.path.splitext(os.path.basename(nuke.scriptName()))[0].split('_')[-2] + '/Light_Fire'), nuke.thisNode())}]\n[knob this.xpos [value this.input0.xpos]]\n[knob this.ypos [value this.input0.ypos]+100]"})
  nuke.setUserPreset("ColorCorrect", "SNJYW/EP04/04/Env_Dream", {'saturation': '0.9', 'selected': 'true', 'note_font': '\xe5\xbe\xae\xe8\xbd\xaf\xe9\x9b\x85\xe9\xbb\x91', 'gain': '1.052840233 1.00316 1.194238067 1', 'label': "SNJYW/EP04/04/Env_Dream\n\xe9\xa2\x84\xe8\xae\xbe\xe9\x94\x81\xe5\xae\x9a :[python {nuke.applyUserPreset('', 'SNJYW/EP04/04/Env_Dream', nuke.thisNode())}]\n\n"})
  nuke.setUserPreset("Grade", "SNJYW/EP04/04/LightFog", {'white': '5', 'black': '0.1134375036 0.1063939929 0.100833334 0.05999999866', 'maskChannelMask': 'rgba.blue', 'gamma': '1.947434425 1.671434402 1.387434483 1', 'label': "[python {str('SNJYW/EP04/' + os.path.splitext(os.path.basename(nuke.scriptName()))[0].split('_')[-2] + '/LightFog')}]\n\xe9\xa2\x84\xe8\xae\xbe\xe9\x94\x81\xe5\xae\x9a :[python {nuke.applyUserPreset('', str('SNJYW/EP04/' + os.path.splitext(os.path.basename(nuke.scriptName()))[0].split('_')[-2] + '/LightFog'), nuke.thisNode())}]\n"})
  nuke.setUserPreset("Grade", "SNJYW/EP04/04/Fog_Lift", {'indicators': '4', 'maskChannelInput': 'rgba.alpha', 'black': '0.05833334103 0.06005333364 0.101333335 0.08500000089', 'note_font': '\xe5\xbe\xae\xe8\xbd\xaf\xe9\x9b\x85\xe9\xbb\x91', 'label': "SNJYW/EP04/04/Fog_Lift\n\xe9\xa2\x84\xe8\xae\xbe\xe9\x94\x81\xe5\xae\x9a :[python {nuke.applyUserPreset('', 'SNJYW/EP04/04/Fog_Lift', nuke.thisNode())}]\n"})
