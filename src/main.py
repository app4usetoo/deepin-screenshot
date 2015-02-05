#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2011 ~ 2014 Deepin, Inc.
#               2011 ~ 2014 Andy Stewart
#
# Author:     Andy Stewart <lazycat.manatee@gmail.com>
# Maintainer: Andy Stewart <lazycat.manatee@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import time
import signal
import tempfile
import subprocess

from PyQt5 import QtCore
from PyQt5.QtCore import QCoreApplication
if os.name == 'posix':
    QCoreApplication.setAttribute(QtCore.Qt.AA_X11InitThreads, True)

from PyQt5.QtQuick import QQuickView
from PyQt5.QtGui import (QSurfaceFormat, QColor, QGuiApplication,
    QPixmap, QCursor, QKeySequence, qRed, qGreen, qBlue)
from PyQt5.QtWidgets import QApplication, qApp, QFileDialog
from PyQt5.QtCore import (pyqtSlot, QStandardPaths, QUrl, QSettings, QVariant,
    QCommandLineParser, QCommandLineOption, QTimer, Qt)
from PyQt5.QtDBus import QDBusConnection, QDBusInterface
from PyQt5.QtMultimedia import QSound
app = QApplication(sys.argv)
app.setOrganizationName("Deepin")
app.setApplicationName("Deepin Screenshot")
app.setApplicationVersion("3.0")
app.setQuitOnLastWindowClosed(False)

from i18n import _
from window_info import WindowInfo
from menu_controller import MenuController
from dbus_services import is_service_exist, unregister_service
from dbus_interfaces import notificationsInterface, socialSharingInterface
from constants import MAIN_QML, SOUND_FILE, MAIN_DIR

def init_cursor_shape_dict():
    global cursor_shape_dict

    file_name_except_extension = lambda x: os.path.basename(x).split(".")[0]

    mouse_style_dir = os.path.join(MAIN_DIR, "image/mouse_style")
    shape_dir = os.path.join(mouse_style_dir, "shape")
    color_pen_dir = os.path.join(mouse_style_dir, "color_pen")

    for _file in os.listdir(shape_dir):
        key = CURSOR_SHAPE_SHAPE_PREFIX + file_name_except_extension(_file)
        cursor_shape_dict[key] = os.path.join(shape_dir, _file)

    for _file in os.listdir(color_pen_dir):
        key = CURSOR_SHAPE_COLOR_PEN_PREFIX + file_name_except_extension(_file)
        cursor_shape_dict[key] = os.path.join(color_pen_dir, _file)

CURSOR_SHAPE_SHAPE_PREFIX = "shape_"
CURSOR_SHAPE_COLOR_PEN_PREFIX = "color_pen_"
SAVE_DEST_TEMP = os.path.join(tempfile.gettempdir() or "/tmp",
                              "DeepinScreenshot-save-tmp.png")
ACTION_ID_OPEN = "id_open"
cursor_shape_dict = {}
init_cursor_shape_dict()

class Window(QQuickView):
    def __init__(self, showOSD=False):
        QQuickView.__init__(self)
        self._showOSD = showOSD

        surface_format = QSurfaceFormat()
        surface_format.setAlphaBufferSize(8)

        self.set_cursor_shape("shape_start_cursor")
        self.setColor(QColor(0, 0, 0, 0))
        self.setFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setResizeMode(QQuickView.SizeRootObjectToView)
        self.setFormat(surface_format)
        self.setTitle(_("Deepin screenshot"))

        self.qpixmap = QGuiApplication.primaryScreen().grabWindow(0)
        self.qpixmap.save("/tmp/deepin-screenshot.png")
        self.qimage = self.qpixmap.toImage()
        self.window_info = WindowInfo()
        self._init_screenshot_config()
        self._soundEffect = QSound(SOUND_FILE)
        self._grabFocusTimer = self._getGrabFocusTimer()

        self._notificationId = None
        self._fileSaveLocation = None
        notificationsInterface.ActionInvoked.connect(self.actionInvoked)
        notificationsInterface.NotificationClosed.connect(self.notificationClosed)

    @pyqtSlot(int, int, result="QVariant")
    def get_color_at_point(self, x, y):
        rgb = self.qimage.pixel(x, y)
        return [qRed(rgb), qGreen(rgb), qBlue(rgb)]

    @pyqtSlot(result="QVariant")
    def get_window_info_at_pointer(self):
        return self.window_info.get_window_info_at_pointer()

    @pyqtSlot(result="QVariant")
    def get_cursor_pos(self):
        return QCursor.pos()

    @pyqtSlot(str)
    def set_cursor_shape(self, shape):
        '''
        Set the shape of cursor, the param shape should be one of the keys
        of the global variable cursor_shape_dict.
        '''
        if cursor_shape_dict.get(shape):
            pix = QPixmap(cursor_shape_dict[shape])
            if shape.startswith(CURSOR_SHAPE_COLOR_PEN_PREFIX):
                cur = QCursor(pix, hotX=0, hotY=pix.height())
            else:
                cur = QCursor(pix, hotX=5, hotY=5)
            self.setCursor(cur)

    @pyqtSlot(str,int,int,int,int)
    def save_overload(self, style, x,y,width,height):
        p = QPixmap.fromImage(self.grabWindow())
        p = p.copy(x,y,width,height)
        image_dir = "/tmp/deepin-screenshot-%s.png" %style
        p.save(os.path.join(image_dir))

    def _getGrabFocusTimer(self):
        timer = QTimer()
        timer.setSingleShot(True)
        timer.setInterval(100)
        timer.timeout.connect(self._grabFocusInternal)
        return timer

    def _grabFocusInternal(self):
        grabPointerStatus = hasattr(self, "_grabPointerStatus") \
                            and self._grabPointerStatus
        grabKeyboardStatus = hasattr(self, "_grabKeyboardStatus") \
                            and self._grabKeyboardStatus
        if not grabPointerStatus:
            self._grabPointerStatus = self.setMouseGrabEnabled(True)
        if not grabKeyboardStatus:
            self._grabKeyboardStatus = self.setKeyboardGrabEnabled(True)

        if not (grabPointerStatus and grabKeyboardStatus):
            self._grabFocusTimer.start()

    def _init_screenshot_config(self):
        settings = QSettings()
        if os.path.exists(settings.fileName()):
            pass
        else:
            '''save the user's last choice of save directory'''
            settings.beginGroup("save")
            settings.setValue("save_op", QVariant(0))
            settings.setValue("folder", QVariant("file folder"))
            settings.endGroup()
            '''save the user's last choice of toolbar directory'''
            settings.beginGroup("common_color_linewidth")
            settings.setValue("color_index", QVariant(3))
            settings.setValue("linewidth_index", QVariant(2))
            settings.endGroup()
            settings.beginGroup("rect")
            settings.setValue("color_index", QVariant(3))
            settings.setValue("linewidth_index", QVariant(2))
            settings.endGroup()
            settings.beginGroup("ellipse")
            settings.setValue("color_index", QVariant(3))
            settings.setValue("linewidth_index", QVariant(2))
            settings.endGroup()
            settings.beginGroup("line")
            settings.setValue("color_index", QVariant(3))
            settings.setValue("linewidth_index", QVariant(2))
            settings.endGroup()
            settings.beginGroup("arrow")
            settings.setValue("color_index", QVariant(3))
            settings.setValue("linewidth_index", QVariant(2))
            settings.endGroup()
            settings.beginGroup("text")
            settings.setValue("color_index", QVariant(3))
            settings.setValue("fontsize_index", QVariant(12))
            settings.endGroup()

    @pyqtSlot(str,str,result="QVariant")
    def get_save_config(self, group_name,op_name):
        settings = QSettings()
        settings.beginGroup(group_name)
        if op_name == "folder":
             op_index = settings.value(op_name)
        else:
             op_index = settings.value(op_name)
        settings.endGroup()
        return op_index

    @pyqtSlot(str,str,str)
    def set_save_config(self,group_name,op_name,op_index):
        settings = QSettings()
        settings.beginGroup(group_name)
        settings.setValue(op_name,QVariant(op_index))
        settings.endGroup()

    def actionInvoked(self, notificationId, actionId):
        if self._notificationId == notificationId:
            if actionId == ACTION_ID_OPEN:
                subprocess.call(["xdg-open", os.path.dirname(self._fileSaveLocation)])

    def notificationClosed(self, notificationId, reason):
        if self._notificationId == notificationId:
            self.closeWindow()

    def copyPixmap(self, pixmap):
        clipboard = QApplication.clipboard()
        clipboard.clear()
        clipboard.setPixmap(pixmap)

        self._notificationId = notificationsInterface.notify("Deepin Screenshot", "Screenshot has been copied to clipboard")

    def savePixmap(self, pixmap, fileName):
        pixmap.save(fileName)
        self._fileSaveLocation = fileName
        self._notificationId = notificationsInterface.notify("Deepin Screenshot", self._fileSaveLocation, [ACTION_ID_OPEN, "Open"])

    @pyqtSlot(int,int,int,int)
    def save_screenshot(self, x, y, width, height):
        save_op = self.get_save_config("save", "save_op")
        save_op_index = int(save_op)

        pixmap = QPixmap.fromImage(self.grabWindow())
        pixmap = pixmap.copy(x, y, width, height)
        fileName = "%s%s.png" % (self.title(), time.strftime("%Y%m%d%H%M%S", time.localtime()))
        pixmap.save(SAVE_DEST_TEMP)

        saveDir = ""
        copy = False
        if save_op_index == 0: #saveId == "save_to_desktop":
            saveDir = QStandardPaths.writableLocation(QStandardPaths.DesktopLocation)
        elif save_op_index == 1: #saveId == "auto_save" :
            saveDir = QStandardPaths.writableLocation(QStandardPaths.PicturesLocation)
        elif save_op_index == 2: #saveId == "save_to_dir":
            saveDir = QFileDialog.getExistingDirectory()
        elif save_op_index == 4: #saveId == "auto_save_ClipBoard":
            copy = True
            saveDir = QStandardPaths.writableLocation(QStandardPaths.PicturesLocation)
        else: copy = True

        self.hide()
        self._soundEffect.play()
        if copy:
            self.copyPixmap(pixmap)
        if saveDir:
            self.savePixmap(pixmap, os.path.join(saveDir, fileName))

    @pyqtSlot()
    def enable_zone(self):
        try:
            iface = QDBusInterface("com.deepin.daemon.Zone", "/com/deepin/daemon/Zone", '', QDBusConnection.sessionBus())
            iface.asyncCall("EnableZoneDetected", True)
        except:
            pass

    @pyqtSlot()
    def disable_zone(self):
        try:
            iface = QDBusInterface("com.deepin.daemon.Zone", "/com/deepin/daemon/Zone", '', QDBusConnection.sessionBus())
            iface.asyncCall("EnableZoneDetected", False)
        except:
            pass

    @pyqtSlot()
    def share(self):
        socialSharingInterface.share("", SAVE_DEST_TEMP)

    @pyqtSlot(int, int, str, result=bool)
    def checkKeySequenceEqual(self, modifier, key, targetKeySequence):
        keySequence = QKeySequence(modifier + key).toString()
        return keySequence == targetKeySequence

    @pyqtSlot(int, int, result=str)
    def keyEventToQKeySequenceString(self, modifier, key):
        keySequence = QKeySequence(modifier + key).toString()
        return keySequence

    def showHotKeyOSD(self):
        self.rootObject().showHotKeyOSD()

    def showWindow(self):
        self.showFullScreen()
        self._grabFocusTimer.start()

    @pyqtSlot()
    def closeWindow(self):
        self.enable_zone()
        unregister_service()
        self.close()
        if self._showOSD:
            self.showHotKeyOSD()
        else:
            qApp.quit()

def main():
    global view
    global menu_controller
    view = Window(startFromDesktopValue)
    menu_controller = MenuController()

    if fullscreenValue:
        desktopWidget = QApplication.desktop()
        pixmap = desktopWidget.grab()
        saveFile = QFileDialog.getSaveFileName(None, _("Save file"), os.path.expanduser("~"))
        if saveFile: pixmap.save(saveFile)
    else:
        qml_context = view.rootContext()
        qml_context.setContextProperty("windowView", view)
        qml_context.setContextProperty("qApp", qApp)
        qml_context.setContextProperty("screenWidth", view.window_info.screen_width)
        qml_context.setContextProperty("screenHeight", view.window_info.screen_height)
        qml_context.setContextProperty("_menu_controller", menu_controller)

        view.setSource(QUrl.fromLocalFile(MAIN_QML))
        view.disable_zone()
        view.showWindow()

if __name__ == "__main__":
    parser = QCommandLineParser()
    parser.addHelpOption()
    parser.addVersionOption()

    delayOption = QCommandLineOption(["d", "delay"],
                                     _("Take a screenshot after NUM seconds"),
                                     "NUM")
    fullscreenOption = QCommandLineOption(["f", "fullscreen"],
                                     _("Take a screenshot of the whole screen"))
    startFromDesktopOption = QCommandLineOption(["i", "icon"],
                                     _("Indicate that this program's started by\
                                        clicking desktop file."))
    parser.addOption(delayOption)
    parser.addOption(fullscreenOption)
    parser.addOption(startFromDesktopOption)
    parser.process(app)

    delayValue = int(parser.value(delayOption) or 0)
    fullscreenValue = bool(parser.isSet(fullscreenOption) or False)
    startFromDesktopValue = bool(parser.isSet(startFromDesktopOption) or False)

    if is_service_exist():
        notificationsInterface.notify("Deepin Screenshot",
            "Deepin Screenshot is running!")
    else:
        QTimer.singleShot(max(0, delayValue * 1000), main)

        signal.signal(signal.SIGINT, signal.SIG_DFL)
        sys.exit(app.exec_())
