import QtQuick

import QGroundControl
import QGroundControl.Controls

// TeamMARS: tool-strip button that shows / hides the optional camera panels
ToolStripAction {
    text:           qsTr("Cameras")
    iconSource:     "/res/PlanSimpleItemCamera.svg"
    visible:        true
    enabled:        true
    onTriggered:    if (globals.teamMarsCameraPanels) globals.teamMarsCameraPanels.toggle()
}
