import QtQuick

import QGroundControl
import QGroundControl.Controls

/// Liquid-glass panel background.
/// Uses only plain Rectangles and gradients (no blur/shader passes) so it adds
/// essentially zero GPU cost and never slows the map, video or telemetry updates.
Rectangle {
    id: root

    /// Tint of the glass body (normally a translucent palette color)
    property color tint:        qgcPal.windowTransparent
    /// Strength of the specular sheen across the top half (0..1)
    property real  sheen:       qgcPal.globalTheme === QGCPalette.Light ? 0.55 : 0.14
    /// Show the bright 1px rim
    property bool  showRim:     true

    color:          tint
    radius:         ScreenTools.defaultBorderRadius * 2
    border.width:   showRim ? 1 : 0
    border.color:   qgcPal.globalTheme === QGCPalette.Light ? Qt.rgba(1, 1, 1, 0.85) : Qt.rgba(1, 1, 1, 0.22)

    QGCPalette { id: qgcPal; colorGroupEnabled: true }

    // Specular sheen: bright at the top edge, fading out by the middle
    Rectangle {
        anchors.fill:       parent
        anchors.margins:    root.border.width
        radius:             Math.max(0, root.radius - root.border.width)
        gradient: Gradient {
            GradientStop { position: 0.0;  color: Qt.rgba(1, 1, 1, root.sheen) }
            GradientStop { position: 0.45; color: Qt.rgba(1, 1, 1, root.sheen * 0.15) }
            GradientStop { position: 1.0;  color: Qt.rgba(1, 1, 1, 0) }
        }
    }

    // Inner shadow along the bottom edge gives the glass some thickness
    Rectangle {
        anchors.left:       parent.left
        anchors.right:      parent.right
        anchors.bottom:     parent.bottom
        anchors.margins:    root.border.width
        height:             Math.min(root.height / 3, ScreenTools.defaultFontPixelHeight)
        radius:             Math.max(0, root.radius - root.border.width)
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.rgba(0, 0, 0, 0) }
            GradientStop { position: 1.0; color: Qt.rgba(0, 0, 0, qgcPal.globalTheme === QGCPalette.Light ? 0.06 : 0.18) }
        }
    }
}
