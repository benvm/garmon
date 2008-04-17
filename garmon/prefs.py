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
from gobject import GObject
import gconf

import garmon
from garmon import GLADE_DIR, debug
from garmon.property_object import PropertyObject, gproperty, gsignal


class PrefsDialog (gtk.Dialog):

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

        color = self._gclient.get_string("/apps/garmon/mil_on_color")
        if not color:
            color = '#F7D30D'
        self._mil_on_colorbutton.set_color(gtk.gdk.color_parse(color))
        self._gconf_ids.append (self._gclient.notify_add ("/apps/garmon/mil_on_color",
                                        self._mil_on_color_notify))

        color = self._gclient.get_string("/apps/garmon/mil_off_color")
        if not color:
            color = '#AAAAAA'
        self._mil_off_colorbutton.set_color(gtk.gdk.color_parse(color))
        self._gconf_ids.append (self._gclient.notify_add ("/apps/garmon/mil_off_color",
                                        self._mil_off_color_notify))
                                                                                 
 
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
        
        self._mil_on_colorbutton = self._glade.get_widget('mil_on_colorbutton')
        self._mil_on_colorbutton.connect('color-set', self._mil_on_color_set)
        
        self._mil_off_colorbutton = self._glade.get_widget('mil_off_colorbutton')
        self._mil_off_colorbutton.connect('color-set', self._mil_off_color_set)


    def _mil_on_color_notify(self, gclient, cnxn_id, entry, args):
        value = entry.value.get_string()
        try:
            self._mil_on_colorbutton.set_color(gtk.gdk.color_parse(value))
        except ValueError:
            debug('We got an invalid colorspec from gconf for mil_on_color')
            self._mil_on_colorbutton.set_color(gtk.gdk.color_parse('#F7D30D'))
            
            
    def _mil_off_color_notify(self, gclient, cnxn_id, entry, args):
        value = entry.value.get_string()
        try:
            self._mil_off_colorbutton.set_color(gtk.gdk.color_parse(value))
        except ValueError:
            debug('We got an invalid colorspec from gconf for mil_off_color')
            self._mil_off_colorbutton.set_color(gtk.gdk.color_parse('#AAAAAA'))

        
    def _mil_on_color_set(self, button):
        color = button.get_color().to_string()
        self._gclient.set_string ("/apps/garmon/mil_on_color", color)
    

    def _mil_off_color_set(self, button):
        color = button.get_color().to_string()
        self._gclient.set_string ("/apps/garmon/mil_off_color", color)
        
                    
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

        

class Preferences(GObject, PropertyObject):
    __gtype_name__ = 'Preferences'

    gproperty('portname', str, '/dev/ttyUSB0', flags=gobject.PARAM_READABLE)
    gproperty('unit-standard', str, 'Metric', flags=gobject.PARAM_READABLE)
    gproperty('save-plugins', bool, True, flags=gobject.PARAM_READABLE)
    gproperty('start-plugins', bool, True, flags=gobject.PARAM_READABLE)
    gproperty('mil_on_color', str, '#F7D30D', flags=gobject.PARAM_READABLE)
    gproperty('mil_off_color', str, '#AAAAAA', flags=gobject.PARAM_READABLE)
    
    def prop_get_portname(self):
        return self._portname
        
    def prop_get_unit_standard(self):
        return self._unit_standard
        
    def prop_get_save_plugins(self):
        return self._save_plugins
        
    def prop_get_start_plugins(self):
        return self._start_plugins
        
    def prop_get_mil_on_color(self):
        return self._mil_on_color
        
    def prop_get_mil_off_color(self):
        return self._mil_off_color


    def __init__(self, gclient):
        GObject.__init__(self)
        PropertyObject.__init__(self)
        
        self._gclient = gclient
        self._gconf_ids = []
        
        self._portname = '/dev/ttyUSB0'
        self._unit_standard = 'Metric'
        self._save_plugins = True
        self._start_plugins = True
        self._mil_on_color = '#F7D30D'
        self._mil_off_color = '#AAAAAA'

        self._gclient.notify_add ("/apps/garmon/port",
                                        self._port_change_notify)
        self._gclient.notify_add ("/apps/garmon/units",
                                        self._units_change_notify)
        self._gclient.notify_add ("/apps/garmon/save_plugins",
                                        self._save_plugins_change_notify)
        self._gclient.notify_add ("/apps/garmon/start_plugins",
                                        self._start_plugins_change_notify)                
        self._gclient.notify_add ("/apps/garmon/mil_on_color",
                                        self._mil_on_color_notify)
        self._gclient.notify_add ("/apps/garmon/mil_off_color",
                                        self._mil_off_color_notify)    

    def __post_init__(self):
        self._gclient.notify("/apps/garmon/port")
        self._gclient.notify("/apps/garmon/units")
        self._gclient.notify("/apps/garmon/save_plugins")
        self._gclient.notify("/apps/garmon/start_plugins")
        self._gclient.notify("/apps/garmon/mil_on_color")
        self._gclient.notify("/apps/garmon/mil_off_color")
        

    def _mil_on_color_notify(self, gclient, cnxn_id, entry, args):
        if entry.value and entry.value.type == gconf.VALUE_STRING:
            value = entry.value.get_string()
        else:
            value = '#F7D30D'
        try:
            gtk.gdk.color_parse(value)
        except ValueError:
            debug('We got an invalid colorspec from gconf for mil_on_color')
            value = '#F7D30D'
        old = self._mil_on_color
        self._mil_on_color = value
        if old != self._mil_on_color:
            self.notify('mil_on_color')
        
            
            
    def _mil_off_color_notify(self, gclient, cnxn_id, entry, args):
        if entry.value and entry.value.type == gconf.VALUE_STRING:
            value = entry.value.get_string()
        else:
            value = '#AAAAAA'
        try:
            gtk.gdk.color_parse(value)
        except ValueError:
            debug('We got an invalid colorspec from gconf for mil_on_color')
            value = '#AAAAAA'
        old = self._mil_off_color
        self._mil_off_color = value
        if old != self._mil_off_color:
            self.notify('mil-off-color')
                    
                    
    def _port_change_notify(self, gclient, cnxn_id, entry, args):
        old = self._portname
        if (not entry.value) or (entry.value.type != gconf.VALUE_STRING):
            self._portname = _("Error!")
        else:
            self._portname = entry.value.get_string()
        if old != self._portname:
            self.notify('portname')
            

    def _units_change_notify(self, gclient, cnxn_id, entry, args):
        old = self._unit_standard
        if (not entry.value) or (entry.value.type != gconf.VALUE_STRING):
            units = 'Metric'
        else:
            units = entry.value.get_string()
        self._unit_standard = units
        if old != self._unit_standard:
            self.notify('unit_standard')

                

    def _save_plugins_change_notify(self, gclient, cnxn_id, entry, args):
        old = self._save_plugins
        self._save_plugins = entry.value.get_bool()
        if old != self._save_plugins:
            self.notify('save_plugins')


    def _start_plugins_change_notify(self, gclient, cnxn_id, entry, args):
        old = self._start_plugins
        self._start_plugins = entry.value.get_bool()
        if old != self._start_plugins:
            self.notify('start_plugins')

     
