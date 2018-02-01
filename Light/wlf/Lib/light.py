# -*- coding=UTF-8 -*-

from pymel.all import (ls, lightlink, setAttr, move, spaceLocator,
                       mel, aimConstraint, autoPlace, rename, modelEditor)


def breakAllLightLink():
    light = ls(selection=True)[0]
    lightlink(b=True, light=light, object=lightlink(query=True, object=light))


def rsPhysicalLight():
    mel.eval('redshiftCreateLight("RedshiftPhysicalLight")')
    light = ls(selection=True)[0]
    setAttr(light + '.colorMode', 1)
    setAttr(light + '.intensity', 10)
    setAttr(light + '.areaVisibleInRender', 0)

    locator = spaceLocator()
    move(locator, (0, 0, -1))
    setAttr(locator + '.inheritsTransform', 0)
    locator.setParent(light)

    aim = aimConstraint(locator, light)
    setAttr(aim + '.aimVector', (0, 0, -1))

    position = autoPlace()
    move(light, position, relative=True)
    move(locator, position, relative=True)

    rename(locator, '{}_aim'.format(light))

    modelEditor('modelPanel4', e=True, lights=True, locators=True)
