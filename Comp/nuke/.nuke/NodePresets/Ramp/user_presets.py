import nuke
def nodePresetsStartup():
  nuke.setUserPreset("ColorCorrect", "Ramp/Cold2Warm", {'selected': 'true', 'gamma': '1.440626025 1.635448456 2.02392602 1', 'contrast': '1.2', 'label': 'Ramp'})
