import nuke
def nodePresetsStartup():
  nuke.setUserPreset("Expression", "1\/z", {'expr0': '(z==0)?1/z:100000', 'channel0': 'depth', 'selected': 'true', 'label': '1/z'})
  nuke.setUserPreset("Expression", "1\z", {'expr0': '(z!=0)?1/z:100000', 'channel0': 'depth', 'selected': 'true', 'label': '1/z'})
