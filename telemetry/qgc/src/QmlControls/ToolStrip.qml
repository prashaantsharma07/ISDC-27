import QtQuick
import QtQuick.Controls

import QGroundControl
import QGroundControl.Controls

Rectangle {
    id:         _root
    color:      "transparent"
    width:      horizontal ? Math.min(maxWidth, toolStripColumn.width + (flickable.anchors.margins * 2)) : ScreenTools.defaultFontPixelWidth * 7
    height:     horizontal ? buttonSize + (flickable.anchors.margins * 2) : Math.min(maxHeight, toolStripColumn.height + (flickable.anchors.margins * 2))
    radius:     ScreenTools.defaultFontPixelWidth / 2

    // Liquid-glass body (drawn beneath the buttons)
    GlassBackground {
        anchors.fill:   parent
        radius:         parent.radius
        z:              -1
    }

    property alias  model:              repeater.model
    property real   maxHeight           ///< Maximum height for control, determines whether text is hidden to make control shorter
    property real   maxWidth:   100000  ///< TeamMARS: maximum width when horizontal
    property bool   horizontal: false   ///< TeamMARS: lay the buttons out in a row (drop panels then open upwards)
    readonly property real buttonSize: ScreenTools.defaultFontPixelWidth * 7 - (ScreenTools.defaultFontPixelWidth * 0.4 * 2)
    property var    fontSize:           ScreenTools.smallFontPointSize

    property var _dropPanel: dropPanel

    function simulateClick(buttonIndex) {
        var button = toolStripColumn.children[buttonIndex]
        if (button.checkable) {
            button.checked = !button.checked
        }
        button.clicked()
    }

    signal dropped(int index)

    DeadMouseArea {
        anchors.fill: parent
    }

    QGCFlickable {
        id:                 flickable
        anchors.margins:    ScreenTools.defaultFontPixelWidth * 0.4
        anchors.fill:       parent
        contentHeight:      toolStripColumn.height
        contentWidth:       toolStripColumn.width
        flickableDirection: _root.horizontal ? Flickable.HorizontalFlick : Flickable.VerticalFlick
        clip:               true

        Grid {
            id:             toolStripColumn
            width:          _root.horizontal ? implicitWidth : flickable.width
            columns:        _root.horizontal ? Math.max(1, repeater.count) : 1
            spacing:        ScreenTools.defaultFontPixelWidth * 0.25

            Repeater {
                id: repeater

                ToolStripHoverButton {
                    id:                 buttonTemplate
                    width:              _root.horizontal ? _root.buttonSize : toolStripColumn.width
                    height:             width
                    radius:             ScreenTools.defaultFontPixelWidth / 2
                    fontPointSize:      _root.fontSize
                    toolStripAction:    modelData
                    dropPanel:          _dropPanel
                    onDropped: (index) => _root.dropped(index)

                    onCheckedChanged: {
                        // We deal with exclusive check state manually since usinug autoExclusive caused all sorts of crazt problems
                        if (checked) {
                            for (var i=0; i<repeater.count; i++) {
                                if (i != index) {
                                    var button = repeater.itemAt(i)
                                    if (button.checked) {
                                        button.checked = false
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    ToolStripDropPanel {
        id:         dropPanel
        toolStrip:  _root
    }
}
