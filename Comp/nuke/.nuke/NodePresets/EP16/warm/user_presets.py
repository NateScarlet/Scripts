import nuke
def nodePresetsStartup():
  nuke.setUserPreset("Grade", "EP16/warm/diffuse", {'note_font': '\xe5\xbe\xae\xe8\xbd\xaf\xe9\x9b\x85\xe9\xbb\x91', 'whitepoint': '1.119017005 0.6712563634 0.6057974696 1', 'selected': 'true', 'indicators': '8', 'multiply': '0.45', 'gl_color': '0x3248ff00', 'white': '2.15 0.9 0.45 1'})
  nuke.setUserPreset("Grade", "EP16/warm/specular", {'gl_color': '0xb932ff00', 'selected': 'true', 'note_font': '\xe5\xbe\xae\xe8\xbd\xaf\xe9\x9b\x85\xe9\xbb\x91'})
  nuke.setUserPreset("Grade", "EP16/warm/SSS", {'note_font': '\xe5\xbe\xae\xe8\xbd\xaf\xe9\x9b\x85\xe9\xbb\x91', 'whitepoint': '2.17578125 0.458984375 0.1888427734 1', 'selected': 'true', 'multiply': '0.66', 'gl_color': '0xff503200', 'white': '2 0.6799996495 0.26 1'})
