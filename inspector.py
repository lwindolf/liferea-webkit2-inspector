#!/usr/bin/python3
# vim:fileencoding=utf-8:sw=4:et
#
# Liferea Plugin to Launch the Webkit2 Inspector
#
# Copyright (C) 2015 Mozbugbox <mozbugbox@yahoo.com.au>
# Copyright (C) 2018 Lars Windolf <lars.windolf@gmx.de>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Library General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Library General Public License for more details.
#
# You should have received a copy of the GNU Library General Public License
# along with this library; see the file COPYING.LIB.  If not, write to
# the Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.
#

import os, io, sys, gi

gi.require_version('WebKit2', '4.0')

from gi.repository import GObject, Gtk, Gdk, PeasGtk, Liferea
from gi.repository import WebKit2

class InspectorWindow:
    """Embed WebKitInspector for a WebKit2 WebView"""
    def __init__(self, wk_view):
        settings = wk_view.get_settings()
        self.old_developer_extras = settings.props.enable_developer_extras
        settings.props.enable_developer_extras = True

        wk_view.connect("key-press-event", self.on_key_press_event)
        wk_view.connect_after("key-press-event", self.on_key_press_event)

        self.inspector = None
        self.wk_view = wk_view

    def on_key_press_event(self, widget, event):
        # for single key press, do `! &` mask keys
        mod_masks = (
                Gdk.ModifierType.SHIFT_MASK
                | Gdk.ModifierType.CONTROL_MASK
                | Gdk.ModifierType.MOD1_MASK
                | Gdk.ModifierType.SUPER_MASK
                )
        single_key = not (event.state & mod_masks)
        if single_key and event.keyval == Gdk.KEY_F12:
            if not self.inspector:
                self.inspector = self.wk_view.get_inspector()
                self.inspector.connect("detach", self.on_finished)
            self.inspector.show()
            return True
        else:
            return False

    def detach_webview(self):
        """On unhook webview, remove signal connections"""
        inspector = self.inspector
        wk_view = self.wk_view

        inspector.disconnect_by_func(self.on_finished)

        settings = self.wk_view.get_settings()
        settings.props.enable_developer_extras = self.old_developer_extras
        self.inspector = None
        self.wk_view = None

    def on_finished(self, inspector, *data):
        self.inspector = None


class InspectorPlugin (GObject.Object, Liferea.ShellActivatable):
    __gtype_name__ = "InspectorPlugin"

    object = GObject.property (type=GObject.Object)
    shell = GObject.property (type=Liferea.Shell)

    _shell = None

    def __init__(self):
        GObject.Object.__init__(self)

    @property
    def main_webkit_view(self):
        """Return the webkit webview in the item_view"""
        shell = self._shell
        item_view = shell.props.item_view
        if not item_view:
            print("Item view not found!")
            return None

        htmlv = item_view.props.html_view
        if not htmlv:
            print("HTML view not found!")
            return None

        return htmlv

    @property
    def current_webviews(self):
        """Get all the available webviews """
        views = []
        webkit_view = self.main_webkit_view
        if webkit_view is None:
            return views
        views.append(webkit_view.props.renderwidget)

        browser_tabs = self._shell.props.browser_tabs
        if browser_tabs.props.tab_info_list != None:
            box_in_tabs = [x.htmlview for x in browser_tabs.props.tab_info_list]
            html_in_tabs = [x.get_widget() for x in box_in_tabs]
            views.extend(html_in_tabs)
        return views

    @property
    def browser_notebook(self):
        """Return the notebook of browser_tabs"""
        browser_tabs = self._shell.props.browser_tabs
        bt_notebook = browser_tabs.props.notebook
        return bt_notebook

    def do_activate (self):
        """Override Peas Plugin entry point"""
        if self._shell is None:
            InspectorPlugin._shell = self.props.shell

        current_views = self.current_webviews
        for v in current_views:
            self.hook_webkit_view(v)

        # watch new webkit view in browser_tabs
        bt_notebook = self.browser_notebook
        cid = bt_notebook.connect("page-added", self.on_tab_added)
        bt_notebook.shades_page_added_cid = cid

    def do_deactivate (self):
        """Peas Plugin exit point"""
        current_views = self.current_webviews
        if current_views:
            for v in current_views:
                self.unhook_webkit_view(v)

        bt_notebook = self.browser_notebook
        bt_notebook.disconnect(bt_notebook.shades_page_added_cid)
        del bt_notebook.shades_page_added_cid

    def on_tab_added(self, noteb, child, page_num, *user_data_dummy):
        """callback for new webview tab creation"""
        # A notebook tab holds a GtkBox with another GtkBox that separates
        # location bar and LifereaHtmlView
        self.hook_webkit_view(child.get_children()[1])

    def hook_webkit_view(self, wk_view):
        wk_view.inspector_window = InspectorWindow(wk_view)

    def unhook_webkit_view(self, wk_view):
        try:
            wk_view.inspector_window.detach_webview()
            del wk_view.inspector_window
        except:
            print("Failed to unhook inspector")

