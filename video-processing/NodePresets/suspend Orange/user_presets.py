import nuke
def nodePresetsStartup():
  nuke.setUserPreset("HueCorrect", "suspend Orange/Emission", {'indicators': '20', 'hue': 'sat {curve 1 0.8412934542 0.2557213306 1 1 1 1}\nlum {curve 1 0.3925373554 0.3925373554 1 1 1 1}\nred {}\ngreen {}\nblue {}\nr_sup {}\ng_sup {}\nb_sup {}\nsat_thrsh {}', 'maskChannelInput': 'Emission.red', 'selected': 'true', 'mix': '0.675'})
