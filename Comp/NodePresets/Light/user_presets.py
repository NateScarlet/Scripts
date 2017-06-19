import nuke
def nodePresetsStartup():
  nuke.setUserPreset("Grade", "Light/Blue", {'white': '1.5', 'selected': 'true', 'black': '0.01600000076 0.02042000368 0.05000000075 0.05000000075', 'label': 'Light/Blue'})
  nuke.setUserPreset("Grade", "Light/White", {'white': '1.5', 'selected': 'true', 'label': 'Light'})
  nuke.setUserPreset("Grade", "Light/Cold", {'maskChannelMask': 'rgba.blue', 'selected': 'true', 'gamma': '0.8824753165 1.200646639 1.133830667 1', 'label': 'ColdLight'})
  nuke.setUserPreset("Grade", "Light/Fire", {'selected': 'true', 'gamma': '1.779999971 1.359029889 0.8009999394 1.779999971', 'label': 'Light/Fire'})
