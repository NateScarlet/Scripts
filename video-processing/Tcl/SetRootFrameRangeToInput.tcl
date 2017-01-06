[
# setRootFrameRangeToInput v0.2
if {([value this.name] == "setRootFrameRangeToInput") && ([class input] == "Read")} {
    knob root.first_frame [value input.origfirst]
    knob root.last_frame [value input.origlast]
    knob root.lock_range 1
} else {
    python nuke.warning('节点无效: [value this.name]')
    return "<font color = red>没连接至读取节点\n或此节点有多个</fonta>"
}
]