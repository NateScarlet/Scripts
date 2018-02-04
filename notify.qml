import QtQuick 1.0

Rectangle {
    id: rect
    width: Math.min(Math.max(150, DATA.text.length * 10), 800)
    height: 100
    radius:10 
    color: "grey"

    Timer {
        running:true
        id: autoclose_timer
        interval: 4000;
        onTriggered: disapear.start()
    }

    Text {
        font{
            family: "微软雅黑,SimHei"
            pointSize: 15
        }
        text: DATA.text
        wrapMode: Text.Wrap
        height: parent.height
        verticalAlignment: Text.AlignVCenter
        horizontalAlignment: Text.AlignHCenter
        anchors.fill: parent
    }

    MouseArea {
        id: mousearea
        hoverEnabled: true
        onEntered: {
            autoclose_timer.stop();
            disapear.stop();
            rect.opacity = 1;
        }
        onExited:autoclose_timer.start()
        anchors.fill: parent

    }

    SequentialAnimation {
        id: disapear
        NumberAnimation { target: rect; property: "opacity"; to: 0; duration: 3000 }
        ScriptAction { script: { mousearea.enabled = false; }
        }
        ScriptAction { script: VIEW.close(); }
    }
}