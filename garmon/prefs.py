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
import random
import string

import gtk
from gtk import glade
import gobject
from gobject import GObject
import gconf

import garmon
from garmon import GLADE_DIR, debug


class PrefsDialog (gtk.Dialog):

    def __init__(self):
        gtk.Dialog.__init__(self, _("Garmon Preferences"), None, 
                                gtk.DIALOG_DESTROY_WITH_PARENT,
                                (gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE,))
                                
        self.set_resizable(False)
        
        self.vbox.set_border_width(5)
        self.vbox.set_spacing(10)
        
        self.notebook = gtk.Notebook()
        self.vbox.pack_start(self.notebook)
    
    def run(self):
        self.show_all()
        gtk.Dialog.run(self)    



class _Preference(object):
    def __init__(self, pname, ptype, default, value=None):
        self.name = pname
        self.ptype = ptype
        self.value = value
        self.default = default
        self.key = None
        self.listeners = []
        
                

class PreferenceManager(GObject):
    __gtype_name__ = 'PreferenceManager'

    def __init__(self, base):
        GObject.__init__(self)
        
        self._gclient = gconf.client_get_default()
        self._gclient.add_dir (base, gconf.CLIENT_PRELOAD_NONE)
        
        self._gconf_ids = []
        
        self._preferences = []
        self._listener_ids = []
                                        
        self._dialog = PrefsDialog()



    def _port_change_notify(self, gclient, cnxn_id, entry, args):
        old = self._portname
        if (not entry.value) or (entry.value.type != gconf.VALUE_STRING):
            self._portname = _("Error!")
        else:
            self._portname = entry.value.get_string()
        if old != self._portname:
            self.notify('portname')
            

    def _gconf_key_change_notify(self, gclient, cnxn_id, entry, pref):
        if entry.value.type == gconf.VALUE_STRING:
            pref.value = entry.value.get_string()
        elif entry.value.type == gconf.VALUE_BOOL:
            pref.value = entry.value.get_bool()
        elif entry.value.type == gconf.VALUE_INT:
            pref.value = entry.value.get_int()
        elif entry.value.type == gconf.VALUE_FLOAT:
            pref.value = entry.value.get_float()

        
        for listener in pref.listeners:
            cb_id, cb, args  = listener
            cb(pref.name, pref.value, pref.ptype, args)
  

    def _pref_notify_cb(self, pname, pvalue, ptype, args):
        widget = args[0]
        if ptype is str:
            if hasattr(widget, 'set_text'):
                widget.set_text(pvalue)
            elif hasattr(widget, 'set_color'):
                widget.set_color(gtk.gdk.color_parse(pvalue))
            else:
                #FIXME: error handling
                pass
        elif ptype is bool:
            if isinstance(widget, gtk.ToggleButton):
                widget.set_active(pvalue)
            else:
                #FIXME: error handling
                pass
            
              
    def _toggle_widget_cb(self, toggle, pname):
        active = toggle.get_active()
        self.set_preference(pname, active)
        
        
    def _text_widget_cb(self, widget, pname):
        value = widget.get_text()
        self.set_preference(pname, value)
        
        
    def _color_widget_cb(self, widget, pname):
        value = widget.get_color().to_string()
        self.set_preference(pname, value)
        
        
    def preference_notify(self, pname):
        for pref in self._preferences:
            if pref.name == pname:
                for listener in pref.listeners:
                    cb_id, cb, args  = listener
                    cb(pref.name, pref.value, pref.ptype, args)


    def preference_notify_add(self, name, cb, *args):
        if not callable(cb):
            raise AttributeError, 'cb should is not callable'
        for pref in self._preferences:
            if pref.name == name:
                unique = False
                while not unique:
                    cb_id = random.randint(1, 1000000)
                    unique = not cb_id in self._listener_ids
                self._listener_ids.append(cb_id)
                pref.listeners.append((cb_id, cb, args))
                return cb_id
        raise ValueError, 'No pref with name "%s" found' % name


    def preference_notify_remove(self, cb_id):
        for pref in self._preferences:
            for listener in pref.listeners:
                if listener[0] == cb_id:
                    pref.listeners.remove(listener)
        if cb_id in self._listener_ids:
            self._listener_ids.remove(cb_id)
   
    
    def get_preference(self, pname):
        for pref in self._preferences:
            if pref.name == pname:
                return pref.value
        raise ValueError, 'No pref with name "%s" found' % pname 
        
    
    def set_preference(self, pname, pvalue):
        for pref in self._preferences:
            if pref.name == pname:
                if not pref.ptype is type(pvalue):
                    raise AttributeError,  \
                          'pvalue should be of %s but is %s instead' \
                          % pref.ptype % type(pvalue)
                pref.value = pvalue
                if pref.ptype is str:
                    self._gclient.set_string(pref.key, pvalue)
                elif pref.ptype is bool:
                    self._gclient.set_bool(pref.key, pvalue)
                elif pref.ptype is int:
                    self._gclient.set_int(pref.key, pvalue)
                elif pref.ptype is float:
                    self._gclient.set_float(pref.key, pvalue)
                return
        raise ValueError, 'No pref with name "%s" found' % name
        
   
    def register_preference(self, pname, ptype, default):
        if not (ptype is str or ptype is bool or ptype is int or ptype is float):
            raise ValueError, 'ptype should be of type str, bool, int or float'
        
        for pref in self._preferences:
            if pref.name == pname:
                raise ValueError, 'a preference with name %s already exists' % pname
                 
        key = string.split(pname, ':')
        key = string.join(key, '/')
        # FIXME!!!!
        key = '/apps/garmon/' + key
        
        if not self._gclient.get(key):
            #No key in gconf yet
            if type(default) is str:
                self._gclient.set_string(key, default)
            elif type(default) is bool:
                self._gclient.set_bool(key, default)
            elif type(default) is int:
                self._gclient.set_int(key, default)
            elif type(default) is float:
                self._gclient.set_float(key, default)
                
        if ptype is str:
            value = self._gclient.get_string(key)
        elif ptype is bool:
            value = self._gclient.get_bool(key)
        elif ptype is int:
            value = self._gclient.get_int(key)
        elif ptype is float:
            value = self._gclient.get_float(key)
        
        pref = _Preference(pname, ptype, default, value)    
        pref.key = key    
        self._preferences.append(pref)
        gconf_id = self._gclient.notify_add(key, self._gconf_key_change_notify, pref)
        self._gconf_ids.append(gconf_id)   
        

    def register_preferences(self, prefs):
        for item in prefs:
            name, ptype, default = item
            self.register_preference(name, ptype, default)


    def show_dialog(self):
        res = self._dialog.run()
        self._dialog.hide()
        
        
    def hide_dialog(self):
        self._dialog.hide()
        
        
    def add_dialog_page(self, xml, root, name):
        top = xml.get_widget(root)
        top.cb_ids = []
        self._dialog.notebook.append_page(top, gtk.Label(name))
        widgets = xml.get_widget_prefix('preference')
        for widget in widgets:
            name = gtk.glade.get_widget_name(widget)[len('preference;'):]
            wtype, ptype, pname = string.split(name, ';')
            if wtype == 'toggle':
                widget.connect('toggled', self._toggle_widget_cb, pname)
            elif wtype == 'text':
                widget.connect('activate', self._text_widget_cb, pname)
            elif wtype == 'color':
                widget.connect('color-set', self._color_widget_cb, pname)
            else:
                #FIXME: should not reach here
                pass
                
            cb_id = self.preference_notify_add(pname, 
                                               self._pref_notify_cb, 
                                               widget)
            top.cb_ids.append(cb_id)
            self.preference_notify(pname)
            
        

        
        
    
    
    
        
