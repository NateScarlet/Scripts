import nuke


def nodePresetsStartup():
    nuke.setUserPreset("Grade", "EP16/warm/specular", {'gl_color': '0xb932ff00',
                                                       'selected': 'true', 'note_font': '\xe5\xbe\xae\xe8\xbd\xaf\xe9\x9b\x85\xe9\xbb\x91'})
    nuke.setUserPreset("Grade", "EP16/warm/SSS", {'multiply': '0.8', 'whitepoint': '1.818201423 0.5457136035 0.3190072179 0.9999997616',
                                                   'white': '1.809999466 0.6799996495 0.5099995136 1', 'note_font': '\xe5\xbe\xae\xe8\xbd\xaf\xe9\x9b\x85\xe9\xbb\x91', 'gl_color': '0xff503200'})
    nuke.setUserPreset("Grade", "EP16/warm/diffuse_cold", {'invert_mask': 'true', 'note_font': '\xe5\xbe\xae\xe8\xbd\xaf\xe9\x9b\x85\xe9\xbb\x91',
                                                            'whitepoint': '0.1410069913 0.3109772801 0.7997316718 1', 'multiply': '0.28', 'gl_color': '0xbdff3200', 'white': '0.4 0.9 1.7 1'})
