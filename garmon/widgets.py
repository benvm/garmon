#!/usr/bin/python
#
# widgets.py
#
# Copyright (C) Ben Van Mechelen 2008-2011 <me@benvm.be>
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



import gobject
from gobject import GObject
import gtk

import garmon
from garmon.property_object import PropertyObject, gproperty
from garmon.sensor import Sensor, Command, StateMixin, UnitMixin, dtc_decode_mil



class MILWidget(gtk.Entry,
                StateMixin,
                PropertyObject):
    __gtype_name__='MILWidget'
    gproperty('on', bool, False)
    gproperty('on-color', str, '#F7D30D')
    gproperty('off-color', str, '#AAAAAA')
    
    def __init__(self, app):
        gtk.Entry.__init__(self, 3)
        self.command = Sensor('0101', 1)
        PropertyObject.__init__(self)

        self._pref_cbs = []
        
        self.app = app
        self.set_text('MIL')
        self.set_property('editable', False)
        self.set_property('width-chars', 3)
        
    def __post_init__(self):
        self.on_color = self.app.prefs.get('mil.on-color')
        self.off_color = self.app.prefs.get('mil.off-color')
        cb_id = self.app.prefs.add_watch('mil.on-color',
                                         self._notify_prefs_cb)
        self._pref_cbs.append(('mil.on-color', cb_id))
        cb_id = self.app.prefs.add_watch('mil.off-color',
                                         self._notify_prefs_cb)
        self._pref_cbs.append(('mil.off-color', cb_id))
                                                     
        self.connect('notify::on', self._notify_cb)
        self.notify('on')
        self.command.connect('notify::data', self._data_changed_cb)
        
    def _notify_cb(self, o, pspec):
        if pspec.name == 'on':
            self._update_color()
        
    def _update_color(self):
        if self.on:
            self.modify_base(gtk.STATE_NORMAL, gtk.gdk.color_parse(self.on_color))
        else:
            self.modify_base(gtk.STATE_NORMAL, gtk.gdk.color_parse(self.off_color))


    def _notify_prefs_cb(self, pname, pvalue, args):
        if pname == 'mil.on-color':
            self.on_color = pvalue
        elif pname == 'mil.off-color':
            self.off_color = pvalue
        self._update_color()
    
    
    def _data_changed_cb(self, command, pspec):
        on = self.command.metric_value == 'On'
        self.on = on
                                  



class BaseView(GObject, StateMixin, PropertyObject):
    __gtype_name__ = 'BaseView'

    gproperty('name-widget', object)
    gproperty('active-widget', object)
    gproperty('value-widget', object)
    gproperty('helper', object)   

    def __init__(self, active_widget=None, name_widget=None,
                       value_widget=None, helper=None):
                       
        GObject.__init__(self)
        PropertyObject.__init__(self, active_widget=active_widget,
                                      name_widget=name_widget,
                                      value_widget=value_widget,
                                      helper=helper)
        
        self._toggleable = False
        if active_widget:
            if isinstance(active_widget, gtk.ToggleButton):
                self._toggleable = True
                self.active = active_widget.get_active()
                active_widget.connect('toggled', self._active_toggled_cb)
            elif isinstance(active_widget, gtk.Button):
                self._togglable = False
                active_widget.connect('clicked', self._active_clicked_cb)
            else:
                raise ValueError, 'active_widget should be gtk.Button or gtk.ToggleButton'
        
        
    def __post_init__(self):
        self.connect('notify::supported', self._notify_supported_cb)
        self.connect('notify::active', self._notify_active_cb)
        self._update_view()
        self._sensitize_widgets()
    

    def _notify_active_cb(self, o, pspec):
        if self._toggleable:
            self.active_widget.set_active(self.active)
        self._sensitize_widgets()
        if not self.active:
            self.command.clear()
        self.emit('active-changed', self.active)
        
    def _active_toggled_cb(self, togglebutton):
        self.active = togglebutton.get_active()
    
    
    def _active_clicked_cb(self, button):
        self.active = not self.active
        
                
    def  _notify_supported_cb(self, o, pspec):
        if not self.supported:
            self.active = False
        self._sensitize_widgets()
    
     
    def _sensitize_widgets(self):
        if self.active_widget:
            self.active_widget.set_sensitive(self.supported)
        for widget in (self.name_widget, self.value_widget):
            if widget:
                widget.set_sensitive(self.supported and self.active)
        self._do_sensitize_widgets()
            
            
    def _data_changed_cb(self, command, pspec):
        self._update_view()
       
       
    def _update_view(self):
        if self.helper and callable(self.helper):
            self.helper(self)
        else:
            self._do_update_view()
            
                    
                    
class CommandView(BaseView):
    __gtype_name__ = 'CommandView'
    
   
    def __init__(self, command, name, active_widget=None,
                       name_widget=None, value_widget=None,
                       units_widget=None, helper=None):
                       
        self.command = Command(command)
        self.command.connect('notify::data', self._data_changed_cb)
        
        BaseView.__init__(self, active_widget, name_widget,
                                value_widget, helper)
        
    def _do_sensitize_widgets(self):
        pass

    def _do_update_view(self):
        data = self.command.data
        if not data:
            data = ''
        if self.value_widget:
            self.value_widget.set_text(data)
            
            
            
class SensorView(BaseView, UnitMixin, PropertyObject):
    __gtype_name__ = 'SensorView'
    
    gproperty('units-widget', object)
    gproperty('update-name', bool, False)
    
    def __init__(self, pid, index=0, units='Metric',
                       active_widget=None, name_widget=None,
                       value_widget=None, units_widget=None,
                       helper=None):
        
        self.command = Sensor(pid, index)
        self.command.connect('notify::data', self._data_changed_cb)
        
        BaseView.__init__(self, active_widget, name_widget,
                                value_widget, helper)
        PropertyObject.__init__(self, active_widget=active_widget,
                                      name_widget=name_widget,
                                      value_widget=value_widget,
                                      units_widget=units_widget,
                                      unit_standard=units,
                                      helper=helper)

    def __post_init__(self):
        self.connect('notify::unit-standard', self._notify_unit_standard_cb)
        BaseView.__post_init__(self)    
       
        
    def  _notify_unit_standard_cb(self, o, pspec):
        self._update_view()
                     
                     
    def _do_sensitize_widgets(self):
        if self.units_widget:
            self.units_widget.set_sensitive(self.supported and self.active)            
       
       
    def _do_update_view(self):
        if self.unit_standard == 'Imperial':
            value = self.command.imperial_value
            units = self.command.imperial_units
        else:
            value = self.command.metric_value
            units = self.command.metric_units
        if not units: units=''
        if not value: value=''
 
        if self.name_widget and self.update_name:
            self.name_widget.set_text(self.command.name)
        if self.value_widget:
            self.value_widget.set_text(value)
        if self.units_widget:
            self.units_widget.set_text(units)
            
            
            
            
class SensorProgressView(BaseView, PropertyObject):
    __gtype_name__ = 'SensorProgressView'
    
    gproperty('progress-widget', object)
    gproperty('min-value', float)
    gproperty('max-value', float)
    gproperty('update-name', bool, False)
        
    def __init__(self, pid, index=0,
                       min_value=0, max_value=100,
                       active_widget=None, name_widget=None,
                       value_widget=None,
                       helper=None, progress_widget=None):
        
        self.command = Sensor(pid, index)
        self.command.connect('notify::data', self._data_changed_cb)
        
        BaseView.__init__(self, active_widget, name_widget,
                                  value_widget, helper)
        PropertyObject.__init__(self, active_widget=active_widget,
                                      name_widget=name_widget,
                                      value_widget=value_widget,
                                      helper=helper,
                                      progress_widget=progress_widget,
                                      min_value=min_value,
                                      max_value=max_value)
                         
                     
    def _do_sensitize_widgets(self):
        if self.progress_widget:
            self.progress_widget.set_sensitive(self.supported and self.active)            
       
       
    def _do_update_view(self):
        value = self.command.metric_value
        if not value: 
            value=''
            fraction = 0
        else:
            fraction = eval(value) / (self.max_value - self.min_value)
            if fraction > 1: fraction = 1
            if fraction < 0: fraction = 0
 
        if self.name_widget and self.update_name:
            self.name_widget.set_text(self.command.name)
        if self.value_widget:
            self.value_widget.set_text(value)
        if self.progress_widget:
            self.progress_widget.set_fraction(fraction)
            

