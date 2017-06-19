import nuke
def nodePresetsStartup():
  nuke.setUserPreset("ColorCorrect", "SNJYW/EP01/01/Env_Warm_AfterExplosion", {'saturation': '0.8', 'gain': '1.550000072 0.9600000381 0.5500000715 1', 'label': "[python {str('SNJYW/EP01/' + os.path.splitext(os.path.basename(nuke.scriptName()))[0].split('_')[-2] + '/Env_Warm_AfterExplosion')}]\n\xe9\xa2\x84\xe8\xae\xbe\xe9\x94\x81\xe5\xae\x9a :[python {nuke.applyUserPreset('', str('SNJYW/EP01/' + os.path.splitext(os.path.basename(nuke.scriptName()))[0].split('_')[-2] + '/Env_Warm_AfterExplosion'), nuke.thisNode())}]\n"})
