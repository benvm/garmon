#!/usr/bin/python
# -*- coding: iso-8859-15 -*-
#
# prefs.py
#
# Copyright (C) Ben Van Mechelen 2007-2009 <me@benvm.be>
#
# This file is part of Garmon 
# 
# Garmon is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, write to:
#   The Free Software Foundation, Inc.,
#   51 Franklin Street, Fifth Floor
#   Boston, MA  02110-1301, USA.

from gettext import gettext as _

import os
import random
import string

import gtk
from gtk import glade
import gobject
from gobject import GObject

from xdg.BaseDirectory import save_config_path
from ConfigParser import RawConfigParser as ConfigParser

import garmon
from garmon import GLADE_DIR, logger

class _PrefsDialog (gtk.Dialog):

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



class _Watch(object):
    def __init__(self, name):
        self.name = name
        self.cb_ids = []

        
                
class PreferenceManager(GObject):
    __gtype_name__ ='PreferenceManager'
    
    def __init__(self):
        GObject.__init__(self)
        
        self._config = ConfigParser()
        self._filename = os.path.join(save_config_path("garmon"), "config")
        self._config.read(self._filename)
        
        self._dialog = _PrefsDialog()
        
        self._watches = []
        

    def _pref_notify_cb(self, pname, pvalue, args):
        widget = args[0]
        if hasattr(widget, 'set_text'):
            widget.set_text(pvalue)
        elif isinstance(widget, gtk.ColorButton):
            widget.set_color(gtk.gdk.color_parse(pvalue))
        elif isinstance(widget, gtk.ToggleButton):
            widget.set_active(bool(pvalue))
        if isinstance(widget, gtk.ComboBox):
            def foreach_cb(model, path, iter):
                value = model.get_value(iter, 0)
                if value == int(pvalue):
                    widget.set_active_iter(iter)
            model = widget.get_model()
            model.foreach(foreach_cb)
            
              
    def _toggle_widget_cb(self, toggle, pname):
        active = toggle.get_active()
        self.set(pname, active)
        
        
    def _text_widget_activate_cb(self, widget, pname):
        value = widget.get_text()
        self.set(pname, value)
        
        
    def _text_widget_focus_out_cb(self, widget, event, pname):
        value = widget.get_text()
        self.set(pname, value)
        
        
    def _color_widget_cb(self, widget, pname):
        value = widget.get_color().to_string()
        self.set(pname, value)
        
        
    def _combo_widget_cb(self, widget, pname):
        iter = widget.get_active_iter()
        if iter:
            value = widget.get_model().get_value(iter, 0)
            self.set(pname, value)
        
        
    def notify(self, name):
        for watch in self._watches:
            if watch.name == name:
                value = self.get(name)
                for cb_id, cb, args in watch.cb_ids:
                    cb(name, value, args)


    def add_watch(self, name, cb, *args):
        if not callable(cb):
            raise AttributeError, 'cb is not callable'
        watch = None
        for item in self._watches:
            if item.name == name:
                watch = item
        if watch is None:
            watch = _Watch(name)
            self._watches.append(watch)
        cb_id = random.randint(1, 1000000)
        watch.cb_ids.append((cb_id, cb, args))
        return cb_id
        

    def remove_watch(self, name, cb_id):
        for watch in self._watches:
            if watch == name:
                for item in cb_ids:
                    if item[0] == cb_id:
                        cb_ids.remove(item)
  
      
    def get(self, name, default=None):
        if not '.' in name:
            section = 'General'
            option = name
        else:
            section, option = name.split('.')
            
        try:
            value = self._config.get(section, option)
        except:
            if default:
                self.set(name, default)
                value = default
            else:
                raise ValueError, 'No pref with name "%s" found and no default value given' % name 
        return value

       
    def set(self, name, value):
        if not '.' in name:
            section = 'General'
            option = name
        else:
            section, option = name.split('.')
        if not self._config.has_section(section):
            self._config.add_section(section)
        self._config.set(section, option, value)
                
    
    def register(self, name, default):
        if not '.' in name:
            section = 'General'
            option = name
        else:
            section, option = name.split('.')
        
        if not self._config.has_section(section):
            self._config.add_section(section)
        if not self._config.has_option(section, option):
            self._config.set(section, option, default)
        
        
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
                widget.connect('activate', self._text_widget_activate_cb, pname)
                widget.connect('focus-out-event', self._text_widget_focus_out_cb, pname)
            elif wtype == 'color':
                widget.connect('color-set', self._color_widget_cb, pname)
            elif wtype == 'combo':
                widget.connect('changed', self._combo_widget_cb, pname)
            else:
                #FIXME: should not reach here
                pass
                
            cb_id = self.add_watch(pname, 
                                   self._pref_notify_cb, 
                                   widget)
            top.cb_ids.append(cb_id)
            self.notify(pname)


    def save(self):
        f = file(self._filename, 'w')
        self._config.write(f)
        f.close()
  




    
if __name__ == '__main__':
    prefs = PreferenceManager()
    prefs.get('General.test', 'foo')
    prefs.save()
    
