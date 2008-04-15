#!/usr/bin/python
# -*- coding: iso-8859-15 -*-
#
# prefs.py
#
# Copyright (C) Ben Van Mechelen 2007-2008 <me@benvm.be>
# 
# prefs.py is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor Boston, MA 02110-1301,  USA

from gettext import gettext as _

import os

import gtk
from gtk import glade
import gobject
import gconf

import garmon
from garmon import GLADE_DIR

class GarmonPrefs (gtk.Dialog):

    def __init__(self, app):
        gtk.Dialog.__init__(self, _("Garmon Preferences"), app, 
                                gtk.DIALOG_DESTROY_WITH_PARENT,
                                (gtk.STOCK_CLOSE,gtk.RESPONSE_ACCEPT))
                                
        self.set_resizable(False)
        
        self._gclient = app.gclient
        self._gconf_ids = []
        
        self.vbox.set_border_width(5)
        self.vbox.set_spacing(10)
        
        self._glade = None
        
        self._setup_gui()
        self._setup_gconf()
        
        self.connect('destroy', self._on_dialog_destroy)
        self.show_all()
        
        
    def _setup_gconf(self):
        port = self._gclient.get_string("/apps/garmon/port")
        if port:
            self._port_entry.set_text(port)
        else:
            #FIXME: gconf schemas not OK: Notify the user
            self._port_entry.set_text(_("Error"))
        self._gconf_ids.append (self._gclient.notify_add ("/apps/garmon/port",
                                        self._port_change_notify))

        units = self._gclient.get_string("/apps/garmon/units")
        if units == 'Metric':
            self._metric_radio.set_active(True)
        else:
            self._imperial_radio.set_active(True)
        self._gconf_ids.append (self._gclient.notify_add ("/apps/garmon/units",
                                      self._units_change_notify))

        active = self._gclient.get_bool('/apps/garmon/save_plugins')
        self._save_plugins_check.set_active(active)
        self._gconf_ids.append (self._gclient.notify_add ("/apps/garmon/save_plugins",
                                                  self._save_plugins_change_notify))
                                                                                                 
        active = self._gclient.get_bool('/apps/garmon/start_plugins')
        self._start_plugins_check.set_active(active)
        self._gconf_ids.append (self._gclient.notify_add ("/apps/garmon/start_plugins",
                                                  self._start_plugins_change_notify))                
 
 
    def _setup_gui(self):
        fname = os.path.join(GLADE_DIR, 'prefs.glade')
        self._glade = gtk.glade.XML(fname, 'prefs_vbox', 'garmon')
        
        self.vbox.pack_start(self._glade.get_widget('prefs_vbox'))
        self._port_entry = self._glade.get_widget('port_entry')
        self._port_entry.connect ("focus_out_event", self._port_entry_commit)
        self._port_entry.connect ("activate", self._port_entry_commit)
        
        self._metric_radio = self._glade.get_widget('metric_radio')
        self._imperial_radio = self._glade.get_widget('imperial_radio')
        self._metric_radio.connect ("toggled", self._units_radio_toggled, 'Metric')
        self._imperial_radio.connect ("toggled", self._units_radio_toggled, 'Imperial')       
        
        self._save_plugins_check = self._glade.get_widget('save_plugins_check')
        self._save_plugins_check.connect('toggled', self._save_plugins_check_toggled)
        
        self._start_plugins_check = self._glade.get_widget('start_plugins_check')
        self._start_plugins_check.connect('toggled', self._start_plugins_check_toggled)
        

    def _port_change_notify(self, gclient, cnxn_id, entry, args):
        if (not entry.value) or (entry.value.type != gconf.VALUE_STRING):
            self._port_entry.set_text (_("Error!"))
        else:
            self._port_entry.set_text (entry.value.get_string())
            
        
    def _port_entry_commit(self, entry, args):
        self._gclient.set_string ("/apps/garmon/port", entry.get_text())
        
        

    def _units_change_notify(self, gclient, cnxn_id, entry, args):
        if (not entry.value) or (entry.value.type != gconf.VALUE_STRING):
            units = 'Metric'
        else:
            units = entry.value.get_string()
        
        if units == 'Metric':
            self._metric_radio.set_active(True)
        else:
            self._imperial_radio.set_active(True)
        

    def _save_plugins_change_notify(self, gclient, cnxn_id, entry, args):
        value = entry.value.get_bool()
        if value:
            self._save_plugins_check.set_active(True)
        else:
            self._save_plugins_check.set_active(False)


    def _start_plugins_change_notify(self, gclient, cnxn_id, entry, args):
        value = entry.value.get_bool()
        if value:
            self._start_plugins_check.set_active(True)
        else:
            self._start_plugins_check.set_active(False)
                        
     
    def _save_plugins_check_toggled(self, toggle):
        active = toggle.get_active()
        self._gclient.set_bool ("/apps/garmon/save_plugins", active)


    def _start_plugins_check_toggled(self, toggle):
        active = toggle.get_active()
        self._gclient.set_bool ("/apps/garmon/start_plugins", active)

        
    def _units_radio_toggled(self, toggle, units):
        if toggle.get_active():
            self._gclient.set_string ("/apps/garmon/units", units)
        
        
        
    def _on_dialog_destroy(self, dialog):
        for id in self._gconf_ids:
            self._gclient.notify_remove (id)

        
        
