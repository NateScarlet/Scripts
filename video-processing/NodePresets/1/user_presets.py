import nuke
def nodePresetsStartup():
  nuke.setUserPreset("Expression", "1\/z", {'expr0': '(z==0)?10000:1/z', 'channel0': 'depth', 'selected': 'true'})
