import QtQuick 1.0

Rectangle {
    width: Math.min(Math.max(150, DATA.text.length * 10), 800)
    height: 100
    radius:10 
    color: "grey"

    Text {
        font{
            family: "微软雅黑,SimHei"
            pointSize: 15
        }
        text: DATA.text
        wrapMode: Text.Wrap
        verticalAlignment: Text.AlignVCenter
        horizontalAlignment: Text.AlignHCenter
        anchors.fill: parent
    }
}