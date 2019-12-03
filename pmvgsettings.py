#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" This file is part of PhotoMVG.

    PhotoMVG is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    PhotoMVG is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with PhotoMVG.  If not, see <http://www.gnu.org/licenses/>."""


from gtktools import *

from gi.repository import Gtk, Gdk, GObject, Pango, GLib
from gi.repository.GdkPixbuf import Pixbuf, InterpType as GdkPixbufInterpType
from gi.repository.GLib import markup_escape_text

from pmvgcommon import *
from pmvgconfig import *
from pmvgtemplates import *
#from pmvgmetadata import FileTypes


class SettingsDialog():
    def wnd_destroy(self, widget):
        Gtk.main_quit()

    def __init__(self, parent, env):
        self.env = env

        resldr = get_resource_loader()
        uibldr = get_gtk_builder(resldr, 'pmvgsettings.ui')
        #
        #
        #
        self.dlg = uibldr.get_object('dlgSettings')
        self.dlg.set_transient_for(parent)


        uibldr.connect_signals(self)

    def run(self):
        self.dlg.show()

        r = self.dlg.run()
        print(r)

        self.dlg.hide()


if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    env = Environment(sys.argv)
    if env.error:
        raise Environment.Error(env.error)

    dlg = SettingsDialog(None, env)
    dlg.run()
