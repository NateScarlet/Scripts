import loadmochaimport
loadmochaimport.load()  # this needs to be done before you try to import mochaimport

import nuke
nuke.pluginAddPath('./icons')

import mochaimport


mochamenu = nuke.menu('Nodes').addMenu(
    'mamoworld/MochaImport+', icon='MochaImport.png')
nuke.menu('Nodes').addCommand('mamoworld/MochaImport+/Stabilized View+',
                              'mochaimport.createStabilizedView()', icon='MiStabilizedView.png')
nuke.menu('Nodes').addCommand('mamoworld/MochaImport+/CornerPin+ w. Lens Dist.',
                              'mochaimport.createCornerPin()', icon='MiCornerPin.png')
mochamenu.addSeparator()
nuke.menu('Nodes').addCommand('mamoworld/MochaImport+/Tracker+',
                              'mochaimport.createTracker4Node()', icon='MiTracker4.png')
nuke.menu('Nodes').addCommand('mamoworld/MochaImport+/Tracker+ (old)',
                              'mochaimport.createTracker3Node()', icon='MiTracker3.png')
nuke.menu('Nodes').addCommand('mamoworld/MochaImport+/RotoPaint+',
                              'mochaimport.createRotoPaintNodeMI()', icon='MiRotoPaint.png')
nuke.menu('Nodes').addCommand('mamoworld/MochaImport+/Roto+',
                              'mochaimport.createRotoNodeMI()', icon='MiRoto.png')
nuke.menu('Nodes').addCommand('mamoworld/MochaImport+/GridWarp+',
                              'mochaimport.createGridWarpNodeMI()', icon='MiGridWarp.png')
nuke.menu('Nodes').addCommand('mamoworld/MochaImport+/SplineWarp+',
                              'mochaimport.createSplineWarpNodeMI()', icon='MiSplineWarp.png')
nuke.menu('Nodes').addCommand('mamoworld/MochaImport+/Transform+',
                              'mochaimport.createTransformNodeMI()', icon='MiMove.png')
mochamenu.addSeparator()
nuke.menu('Nodes').addCommand('mamoworld/MochaImport+/Camera and Geo+',
                              'mochaimport.createCameraAndPointCloud()', icon='MiCameraAndGeo.png')
nuke.menu('Nodes').addCommand('mamoworld/MochaImport+/Full camera rig+',
                              'mochaimport.createCameraRig()', icon='MiFullCameraRig.png')
mochamenu.addSeparator()
nuke.menu('Nodes').addCommand('mamoworld/MochaImport+/Settings',
                              'mochaimport.showSettings()', icon='MiSettings.png')
