import nuke
def nodePresetsStartup():
  nuke.setUserPreset("Grade", "Fog/Blue", {'selected': 'true', 'label': 'Fog', 'mix': '0.2', 'black': '0.01', 'indicators': '16', 'white': '2', 'gamma': '0.6897417903 1.091919184 1.564040422 1'})
  nuke.setUserPreset("Grade", "Fog/Orange", {'white': '5', 'selected': 'true', 'black': '0.3554133177 0.1599360257 0 0.3199999928', 'add': '0.07999999821 0.05123200268 0.03039999865 0.07999999821', 'gamma': '0.6'})
  nuke.setUserPreset("Grade", "Fog/Orange2", {'white': '1.6', 'selected': 'true', 'black': '0.05', 'gamma': '1.348044395 0.9166702628 0.6740221977 1', 'label': 'Fog/Orange'})
  nuke.setUserPreset("Grade", "Fog/Yellow", {'white': '1.6', 'selected': 'true', 'black': '0.05', 'gamma': '1.183000326 1.04370153 0.7732982039 1', 'label': 'Fog/Yellow'})
