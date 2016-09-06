#NoEnv  ; Recommended for performance and compatibility with future AutoHotkey releases.
; #Warn  ; Enable warnings to assist with detecting common errors.
SendMode Input  ; Recommended for new scripts due to its superior speed and reliability.
SetWorkingDir %A_ScriptDir%  ; Ensures a consistent starting directory.

i = 101

$^v::
Loop, 100 {
    gosub main
    Sleep, 0
    Sleep, 100
}
main:
i -= 1
Clipboard = 
(
set cut_paste_input [stack 0]
version 10.0 v1
Read {
 inputs 0
 file "\[python \{image(%i%)\}]"
}
clone node28b66400|Transform|2904 Transform {
 translate {0 40}
 center {1024 778}
 name Transform2
 selected true
 xpos 8430
 ypos -562
}
clone node28b66000|Reformat|2904 Reformat {
 format "1920 1160 0 0 1920 1160 1 bbb"
 name Reformat1
 selected true
 xpos 8430
 ypos -520
}
clone node2ad17800|Text2|2904 Text2 {
 font_size_toolbar 100
 font_width_toolbar 100
 font_height_toolbar 100
 message "\[lrange \[split \[basename \[metadata input/filename]] ._] 3 3]?"
 old_message {{63}
   }
 old_expression_markers {{0 -1}
   }
 box {0 0 0 80}
 transforms {{0 2}
   }
 cursor_position 61
 scale {1 1}
 cursor_initialised true
 autofit_bbox false
 initial_cursor_position {{0 1080}
   }
 group_animations {{0} imported: 0 selected: items: "root transform/"}
 animation_layers {{1 11 1024 778 0 0 1 1 0 0 0 0}
   }
 color {0.145 0.15 0.14 1}
 color_panelDropped true
 name Text1
 selected true
 xpos 8430
 ypos -466
}

)
Send, ^v
return

$esc::
ExitApp