import nuke
def nodePresetsStartup():
  nuke.setUserPreset("ColorCorrect", "Color/Fog_Fire", {'indicators': '8', 'selected': 'true', 'gain': '2.574195862 1.314195871 0.3741958141 4', 'label': 'Color/Fog_Fire'})
  nuke.setUserPreset("Grade", "Color/hue0.611", {'indicators': '16', 'mix': '0.19', 'selected': 'true', 'gamma': '0.723744452 0.9312467575 1.345008731 1', 'label': 'Color'})
  nuke.setUserPreset("Grade", "Color/Hue0.575", {'selected': 'true', 'gamma': '0.6529203057 1.07289505 1.274184585 1', 'label': 'Color'})
  nuke.setUserPreset("Grade", "Color/Hue0.065", {'selected': 'true', 'gamma': '1.333411813 0.9544405937 0.7121475339 1', 'label': 'Color'})
