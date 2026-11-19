import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtMultimedia
import QtCore

import QGroundControl
import QGroundControl.Controls

/// TeamMARS: two optional camera feeds along the right edge (one top, one bottom).
///
/// * Off by default; toggled from the "Cameras" button in the tool strip. Everything is remembered.
/// * Each panel plays any stream FFmpeg understands: rtsp://, udp://, http(s):// MJPEG/HLS, files.
///   Panel 2 defaults to the TeamMARS vision helper (YOLO / OpenCV overlay) on this PC.
/// * Per panel: flip (upside-down), mirror (left/right), change URL. Panels can be swapped and resized.
/// * Uses Qt Multimedia (separate from QGC's own video pipeline), low-latency mode, no audio,
///   and it retries automatically if a stream drops — it can never block telemetry or the map.
Item {
    id: root

    property real   margin:         ScreenTools.defaultFontPixelWidth * 0.75
    property real   panelWidth:     Math.max(ScreenTools.defaultFontPixelWidth * 26,
                                             Math.min(parent ? parent.width * _sizes[settings.sizeIndex] : 0, ScreenTools.defaultFontPixelWidth * 64))
    property real   panelHeight:    panelWidth * 9 / 16
    property bool   active:         settings.enabled
    readonly property real rightEdgeInset: active ? panelWidth + margin : 0

    readonly property var _sizes: [0.16, 0.21, 0.28]

    visible:    active
    width:      panelWidth

    function toggle() { settings.enabled = !settings.enabled }

    Settings {
        id:         settings
        category:   "TeamMARSCameras"

        property bool   enabled:    false
        property string url1:       ""
        property string url2:       "http://127.0.0.1:8090/stream.mjpg"
        property bool   flip1:      false
        property bool   mirror1:    false
        property bool   flip2:      false
        property bool   mirror2:    false
        property bool   swapped:    false
        property int    sizeIndex:  1
    }

    CameraPanel {
        id:             topPanel
        anchors.top:    parent.top
        anchors.right:  parent.right
        slot:           settings.swapped ? 2 : 1
    }

    CameraPanel {
        id:             bottomPanel
        anchors.bottom: parent.bottom
        anchors.right:  parent.right
        slot:           settings.swapped ? 1 : 2
    }

    component PanelButton: Rectangle {
        id:             pb
        property string label
        property bool   on:     false
        signal clicked

        implicitWidth:  pbLabel.implicitWidth + ScreenTools.defaultFontPixelWidth
        implicitHeight: pbLabel.implicitHeight + ScreenTools.defaultFontPixelHeight * 0.3
        radius:         height / 2
        color:          on ? qgcPal.buttonHighlight : Qt.rgba(0, 0, 0, 0.45)
        border.color:   Qt.rgba(1, 1, 1, 0.35)
        border.width:   1

        QGCLabel {
            id:                 pbLabel
            anchors.centerIn:   parent
            text:               pb.label
            font.pointSize:     ScreenTools.smallFontPointSize
            color:              pb.on ? qgcPal.buttonHighlightText : "white"
        }
        MouseArea {
            anchors.fill:   parent
            onClicked:      pb.clicked()
        }
    }

    component CameraPanel: Item {
        id:         panel
        width:      root.panelWidth
        height:     root.panelHeight

        property int    slot:   1     // which stream settings this panel shows
        readonly property string url:    slot === 1 ? settings.url1 : settings.url2
        readonly property bool   flip:   slot === 1 ? settings.flip1 : settings.flip2
        readonly property bool   mirror: slot === 1 ? settings.mirror1 : settings.mirror2
        readonly property bool   playing: player.playbackState === MediaPlayer.PlayingState && player.hasVideo

        function setFlip(v)   { if (slot === 1) settings.flip1 = v;   else settings.flip2 = v }
        function setMirror(v) { if (slot === 1) settings.mirror1 = v; else settings.mirror2 = v }
        function setUrl(v)    { if (slot === 1) settings.url1 = v;    else settings.url2 = v }

        // Glass frame
        GlassBackground {
            anchors.fill:   parent
            radius:         ScreenTools.defaultFontPixelWidth
        }

        Rectangle {
            id:                 videoClip
            anchors.fill:       parent
            anchors.margins:    2
            radius:             ScreenTools.defaultFontPixelWidth * 0.8
            color:              "black"
            clip:               true

            VideoOutput {
                id:             videoOut
                anchors.fill:   parent
                fillMode:       VideoOutput.PreserveAspectFit
                transform: Scale {
                    origin.x:   videoOut.width / 2
                    origin.y:   videoOut.height / 2
                    xScale:     panel.mirror ? -1 : 1
                    yScale:     panel.flip ? -1 : 1
                }
            }
        }

        MediaPlayer {
            id:             player
            source:         panel.url
            videoOutput:    videoOut
            loops:          MediaPlayer.Infinite

            Component.onCompleted: {
                try { player.playbackOptions.playbackIntent = PlaybackOptions.LowLatencyStreaming } catch (e) { }
                if (panel.url !== "" && root.active) player.play()
            }
            onSourceChanged: if (panel.url !== "" && root.active) player.play()
        }

        Connections {
            target: root
            function onActiveChanged() { if (root.active && panel.url !== "") player.play(); else player.stop() }
        }

        // Reconnect automatically if the stream drops or the camera boots after us
        Timer {
            interval:   3000
            repeat:     true
            running:    root.active && panel.url !== "" && !panel.playing
            onTriggered: { player.stop(); player.play() }
        }

        // Status text when there is no picture
        QGCLabel {
            anchors.centerIn:       parent
            width:                  parent.width * 0.9
            horizontalAlignment:    Text.AlignHCenter
            wrapMode:               Text.WordWrap
            color:                  "white"
            font.pointSize:         ScreenTools.smallFontPointSize
            visible:                !panel.playing
            text:                   panel.url === "" ? qsTr("Camera %1\nNo stream set — hover and press URL").arg(panel.slot)
                                                     : qsTr("Camera %1\nConnecting…\n%2").arg(panel.slot).arg(panel.url)
        }

        // Title chip
        Rectangle {
            anchors.left:       parent.left
            anchors.top:        parent.top
            anchors.margins:    ScreenTools.defaultFontPixelWidth * 0.6
            width:              titleLabel.implicitWidth + ScreenTools.defaultFontPixelWidth
            height:             titleLabel.implicitHeight + 2
            radius:             height / 2
            color:              Qt.rgba(0, 0, 0, 0.45)

            QGCLabel {
                id:                 titleLabel
                anchors.centerIn:   parent
                text:               qsTr("CAM %1").arg(panel.slot) + (panel.playing ? "  ●" : "")
                color:              panel.playing ? "#9CE3C3" : "white"
                font.pointSize:     ScreenTools.smallFontPointSize
            }
        }

        HoverHandler { id: hover }

        // Controls appear on hover so the picture stays clean
        Flow {
            anchors.left:       parent.left
            anchors.right:      parent.right
            anchors.bottom:     parent.bottom
            anchors.margins:    ScreenTools.defaultFontPixelWidth * 0.6
            spacing:            ScreenTools.defaultFontPixelWidth * 0.5
            visible:            hover.hovered || urlField.visible
            layoutDirection:    Qt.RightToLeft

            PanelButton { label: qsTr("Flip");   on: panel.flip;   onClicked: panel.setFlip(!panel.flip) }
            PanelButton { label: qsTr("Mirror"); on: panel.mirror; onClicked: panel.setMirror(!panel.mirror) }
            PanelButton { label: qsTr("Swap");                     onClicked: settings.swapped = !settings.swapped }
            PanelButton { label: qsTr("Size");                     onClicked: settings.sizeIndex = (settings.sizeIndex + 1) % root._sizes.length }
            PanelButton { label: qsTr("URL");    on: urlField.visible; onClicked: { urlField.text = panel.url; urlField.visible = !urlField.visible; if (urlField.visible) urlField.forceActiveFocus() } }
        }

        QGCTextField {
            id:                 urlField
            anchors.left:       parent.left
            anchors.right:      parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.margins:    ScreenTools.defaultFontPixelWidth
            visible:            false
            placeholderText:    "rtsp://192.168.144.25:8554/main.264"
            onAccepted:         { panel.setUrl(text.trim()); visible = false }
            onEditingFinished:  visible = false
        }

        // Double-click: quickly enlarge / shrink
        TapHandler {
            onDoubleTapped: settings.sizeIndex = settings.sizeIndex === root._sizes.length - 1 ? 1 : root._sizes.length - 1
        }
    }

    QGCPalette { id: qgcPal; colorGroupEnabled: true }
}
