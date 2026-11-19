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
/// * Each panel is half the map height (top half / bottom half); "Size" changes the width.
/// * Per panel: fill/fit, flip (upside-down), mirror (left/right), change URL. Panels can be swapped and resized.
/// * Uses Qt Multimedia (separate from QGC's own video pipeline), low-latency mode, no audio,
///   and it retries automatically if a stream drops — it can never block telemetry or the map.
Item {
    id: root

    property real   margin:         ScreenTools.defaultFontPixelWidth * 0.75
    property real   panelWidth:     Math.max(ScreenTools.defaultFontPixelWidth * 26,
                                             Math.min(parent ? parent.width * _sizes[settings.sizeIndex] : 0, ScreenTools.defaultFontPixelWidth * 64))
    // TeamMARS: the two panels share the full height of the map — each gets one half
    property real   panelHeight:    Math.max(0, (height - margin) / 2)
    property bool   active:         settings.enabled
    readonly property real rightEdgeInset: active ? panelWidth + margin : 0

    readonly property var _sizes: [0.16, 0.21, 0.28]

    visible:    active
    width:      panelWidth

    function toggle() { settings.enabled = !settings.enabled }

    MediaDevices { id: mediaDevices }

    /// Camera device whose id (on Linux: /dev/videoN) matches path, or null
    function findVideoInput(path) {
        var inputs = mediaDevices.videoInputs
        for (var i = 0; i < inputs.length; i++) {
            if (inputs[i].id === path || String(inputs[i].id).indexOf(path) >= 0) {
                return inputs[i]
            }
        }
        return null
    }

    /// Cycle a panel through the USB capture devices (skips the laptop's built-in webcam last)
    function nextUsbUrl(current) {
        var inputs = mediaDevices.videoInputs
        var ids = []
        for (var i = 0; i < inputs.length; i++) {
            if (String(inputs[i].description).indexOf("Integrated") < 0) ids.push(String(inputs[i].id))
        }
        for (i = 0; i < inputs.length; i++) {
            if (String(inputs[i].description).indexOf("Integrated") >= 0) ids.push(String(inputs[i].id))
        }
        if (ids.length === 0) return current
        var cur = current.indexOf("usb:") === 0 ? current.substring(4) : ""
        var next = (ids.indexOf(cur) + 1) % ids.length
        return "usb:" + ids[next]
    }

    /// Prefer MJPEG (fast over USB) at the highest frame rate, up to 1280x720 (fits two cameras on one USB 2.0 bus)
    function pickFormat(cam) {
        var formats = cam.cameraDevice.videoFormats
        var best = null, bestScore = -1
        for (var i = 0; i < formats.length; i++) {
            var f = formats[i]
            // cap at 1280x720: two USB 2.0 grabbers at 1280x1024@60 exceed the bus ("No space left on device")
            if (f.resolution.width > 1280 || f.resolution.height > 720) continue
            // 29 = QVideoFrameFormat::Format_Jpeg (MJPEG); the enum is not exposed to QML
            var score = f.maxFrameRate * 100000 + f.resolution.width * f.resolution.height / 100 + (f.pixelFormat === 29 ? 50000000 : 0)
            if (score > bestScore) { bestScore = score; best = f }
        }
        if (best) cam.cameraFormat = best
    }

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
        property bool   fill1:      true    // true: fill the tall panel (trims the sides), false: show the whole frame
        property bool   fill2:      true
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
        readonly property bool   fill:   slot === 1 ? settings.fill1 : settings.fill2
        // USB capture devices (FPV receiver / HDMI grabbers): "usb:/dev/video2"
        readonly property bool   isUsb:   url.indexOf("usb:") === 0 || url.indexOf("/dev/video") === 0
        readonly property string usbPath: url.indexOf("usb:") === 0 ? url.substring(4) : url
        readonly property var    usbDevice: isUsb ? root.findVideoInput(usbPath) : null
        // a USB device can only be opened once: if both panels pick the same one, panel 2 stands down
        readonly property bool   usbConflict: isUsb && slot === 2 && settings.url1 === url
        // start the panels one after the other: two USB cameras starting at the same instant can fail
        property bool _startReady: false
        Timer { interval: 300 + panel.slot * 1200; running: true; onTriggered: panel._startReady = true }
        // USB counts as live only once frames actually arrive (VideoOutput learns the frame size)
        readonly property bool   playing: isUsb ? (usbCamera.active && usbDevice !== null && videoOut.sourceRect.width > 0)
                                                : (player.playbackState === MediaPlayer.PlayingState && player.hasVideo)

        function setFlip(v)   { if (slot === 1) settings.flip1 = v;   else settings.flip2 = v }
        function setMirror(v) { if (slot === 1) settings.mirror1 = v; else settings.mirror2 = v }
        function setFill(v)   { if (slot === 1) settings.fill1 = v;   else settings.fill2 = v }
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
                fillMode:       panel.fill ? VideoOutput.PreserveAspectCrop : VideoOutput.PreserveAspectFit
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
            source:         panel.isUsb ? "" : panel.url
            videoOutput:    panel.isUsb ? null : videoOut
            loops:          MediaPlayer.Infinite

            Component.onCompleted: {
                try { player.playbackOptions.playbackIntent = PlaybackOptions.LowLatencyStreaming } catch (e) { }
                if (panel.url !== "" && !panel.isUsb && root.active) player.play()
            }
            onSourceChanged: if (panel.url !== "" && !panel.isUsb && root.active) player.play()
        }

        // USB capture: Qt camera on the chosen /dev/videoN, fastest MJPEG mode up to 1280x720
        CaptureSession {
            camera: Camera {
                id:             usbCamera
                cameraDevice:   panel.usbDevice ? panel.usbDevice : mediaDevices.defaultVideoInput
                active:         root.active && panel.isUsb && panel.usbDevice !== null && !panel.usbConflict && panel._startReady
                // compressed MJPEG mode before streaming: two uncompressed 1080p USB feeds do not fit on one USB 2.0 bus
                onCameraDeviceChanged:  root.pickFormat(usbCamera)
                Component.onCompleted:  root.pickFormat(usbCamera)
                onActiveChanged:        if (active) root.pickFormat(usbCamera)
            }
            videoOutput: panel.isUsb ? videoOut : null
        }

        Connections {
            target: root
            function onActiveChanged() { if (root.active && panel.url !== "" && !panel.isUsb) player.play(); else player.stop() }
        }

        // Reconnect automatically if the stream drops or the camera boots after us
        Timer {
            interval:   3000
            repeat:     true
            running:    root.active && panel.url !== "" && !panel.playing && !panel.usbConflict
            onTriggered: {
                if (panel.isUsb) { usbCamera.active = false; usbCamera.active = Qt.binding(function() { return root.active && panel.isUsb && panel.usbDevice !== null && !panel.usbConflict && panel._startReady }) }
                else { player.stop(); player.play() }
            }
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
            text:                   panel.url === "" ? qsTr("Camera %1\nNo stream set — hover and press USB or URL").arg(panel.slot)
                                    : (panel.isUsb && panel.usbDevice === null) ? qsTr("Camera %1\nUSB device %2 not found — press USB").arg(panel.slot).arg(panel.usbPath)
                                    : panel.usbConflict ? qsTr("Camera %1\n%2 is already used by Camera 1 — press USB for the other one").arg(panel.slot).arg(panel.usbPath)
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

            PanelButton { label: panel.fill ? qsTr("Fill") : qsTr("Fit"); on: panel.fill; onClicked: panel.setFill(!panel.fill) }
            PanelButton { label: qsTr("Flip");   on: panel.flip;   onClicked: panel.setFlip(!panel.flip) }
            PanelButton { label: qsTr("Mirror"); on: panel.mirror; onClicked: panel.setMirror(!panel.mirror) }
            PanelButton { label: qsTr("Swap");                     onClicked: settings.swapped = !settings.swapped }
            PanelButton { label: qsTr("Size");                     onClicked: settings.sizeIndex = (settings.sizeIndex + 1) % root._sizes.length }
            PanelButton { label: qsTr("USB");    on: panel.isUsb;  onClicked: panel.setUrl(root.nextUsbUrl(panel.url)) }
            PanelButton { label: qsTr("URL");    on: urlField.visible; onClicked: { urlField.text = panel.url; urlField.visible = !urlField.visible; if (urlField.visible) urlField.forceActiveFocus() } }
        }

        QGCTextField {
            id:                 urlField
            anchors.left:       parent.left
            anchors.right:      parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.margins:    ScreenTools.defaultFontPixelWidth
            visible:            false
            placeholderText:    "rtsp://192.168.144.25:8554/main.264  or  usb:/dev/video2"
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
