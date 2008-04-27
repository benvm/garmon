#!/usr/bin/python
#
# live_data.py
#
# Copyright (C) Ben Van Mechelen 2007-2008 <me@benvm.be>
# 
# livedata.py is free software; you can redistribute it and/or modify
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

import os
from gettext import gettext as _

import gobject
from gobject import GObject
import gtk
from gtk import glade

import garmon
import garmon.plugin
import garmon.sensor

from garmon.property_object import PropertyObject, gproperty, gsignal
from garmon.plugin import Plugin, STATUS_STOP, STATUS_WORKING, STATUS_PAUSE
from garmon.obd_device import OBDDataError, OBDPortError, get_sensor_units
from garmon.sensor import StateMixin, UnitMixin, SensorProxyMixin
from garmon.widgets import MILWidget


__name = _('Live Data')
__version = '0.1.1'
__author = 'Ben Van Mechelen'
__description = _('View the most imported live data like:\n *Fuel System\n *Intake\n *VIN\n *...\n')
__class = 'LiveData'


class LiveData (Plugin, gtk.VBox):
    __gtype_name__='LiveData'
    def __init__ (self, app):
        gtk.VBox.__init__(self)

        self.app = app
        
        self._pref_cbs = []
        self._app_cbs = []
        self._notebook_cbs = []
        self._scheduler_cbs = []
        self._obd_cbs = []
        
        if app.prefs.get_preference('imperial'):
            self._unit_standard = 'Imperial'
        else:
            self._unit_standard = 'Metric'
            
        cb_id = app.prefs.preference_notify_add('imperial', 
                                                self._notify_units_cb)
        self._pref_cbs.append(cb_id)

        self.status = STATUS_STOP

        self.views = []
        self.os_views = []

        self._setup_gui()
        self._setup_sensors()

        self._obd_cbs.append(app.obd.connect('connected', 
                                             self._obd_connected_cb))
        self._notebook_cbs.append(app.notebook.connect('switch-page', 
                                                  self._notebook_page_change_cb))
        
        self._scheduler_cbs.append(self.app.scheduler.connect('notify::working',
                                             self._scheduler_notify_working_cb))
        
    
    def _setup_gui(self):
        dirname = os.path.dirname(__file__)
        filename = os.path.join(dirname, 'live_data.glade')
        self.glade_xml = glade.XML(filename, 'main_hbox')
        main_hbox = self.glade_xml.get_widget('main_hbox')
        self.pack_start(main_hbox)
        main_hbox.show_all()
        self.show_all()
        
        
    def _setup_sensors(self):

        self.views = []
        self.os_views = []

        xml = self.glade_xml

        mil = MILWidget(self.app)
        #FIXME: change colors according to gconf
        mil.connect('active-changed', self._view_active_changed_cb)
        xml.get_widget('mil_alignment').add(mil)
        self.views.append(mil)

        for item in SENSORS: 
            label = button = entry = unit = None
            pid = item[PID]
            index = item[INDEX]
            if item[LABEL]:
                label = xml.get_widget(item[LABEL])
            if item[BUTTON]:
                button = xml.get_widget(item[BUTTON])
            if item[ENTRY]:
                entry = xml.get_widget(item[ENTRY])
            if item[UNIT]:
                unit = xml.get_widget(item[UNIT])
            func = (item[HELPER])
            
            view = LiveDataView(pid, index, units=self._unit_standard,
                       active_widget=button, name_widget=label,
                       value_widget=entry, units_widget=unit,
                       helper=func)
                       
            view.connect('active-changed', self._view_active_changed_cb)
            
            if item[ONE_SHOT]:
                self.os_views.append(view)
            else:
                self.views.append(view)
    
    
    def _scheduler_notify_working_cb(self, scheduler, pspec):
        if not scheduler.working:
            for views in (self.views, self.os_views):
                for view in views:
                    view.sensor.clear()
        else:
            for view in self.os_views:
                if view.active:
                    self.app.scheduler.add(view.sensor, True)
                    
            
    def _view_active_changed_cb(self, view, active):
        if active:    
            if self.status == STATUS_WORKING:
                self.app.scheduler.add(view.sensor)
        else:
            self.app.scheduler.remove(view.sensor)
    
    
    def _update_supported_views(self):
        print 'in _update_supported_views'
        for views in (self.views, self.os_views):
            for view in views:
                if self.app.obd:
                    if view.sensor.pid in self.app.obd.supported_pids:
                        view.supported=True
                        view.active=True
                    else:
                        view.supported=False
                else:
                    view.supported=False
   
            
    def start(self):
        if not self.status == STATUS_WORKING:
            for view in self.views:
                if view.active:
                    self.app.scheduler.add(view.sensor, False)
            for view in self.os_views:
                if view.active:
                    self.app.scheduler.add(view.sensor, True)
            self.status = STATUS_WORKING
            
            
    def stop(self):
        if not self.status == STATUS_STOP:
            for views in (self.views, self.os_views):
                for view in views:
                    self.app.scheduler.remove(view.sensor)
                    view.sensor.clear()
            self.status = STATUS_STOP
        
        
    def _obd_connected_cb(self, obd, connected):
        page = self.app.notebook.get_current_page()
        visible = self.app.notebook.get_nth_page(page) is self
        if visible:
            self.stop()
        self._update_supported_views()
        for view in self.os_views:
            if view.active:
                self.app.scheduler.add(view.sensor, True)
        if visible:
            self.start()


    def _notify_units_cb(self, pname, pvalue, ptype, args):
        if pname == 'imperial' and pvalue:
            self._unit_standard = 'Imperial'
        else:
            self._unit_standard = 'Metric'
        
        for views in (self.views, self.os_views):
            for view in self.views:
                view.unit_standard = self._unit_standard
            
            
    def _notebook_page_change_cb (self, notebook, no_use, page):
        plugin = notebook.get_nth_page(page)
        if plugin is self:
            self.start()
        else:
            self.stop()
            
    def load(self):
        self.app.notebook.append_page(self, gtk.Label(_('Live Data')))            
            
    def unload(self):
        self.app.notebook.remove(self)
        for cb_id in self._pref_cbs:
            self.app.prefs.preference_notify_remove(cb_id)
        for cb_id in self._app_cbs:
            self.app.disconnect(cb_id)
        for cb_id in self._notebook_cbs:
            self.app.notebook.disconnect(cb_id)
        for cb_id in self._scheduler_cbs:
            self.app.scheduler.disconnect(cb_id)
        for cb_id in self._obd_cbs:
            self.app.obd.disconnect(cb_id)

class LiveDataView(GObject, SensorProxyMixin, 
                            StateMixin, UnitMixin, 
                            PropertyObject):
    __gtype_name__ = 'LiveDataView'
    
    gproperty('name-widget', object)
    gproperty('active-widget', object)
    gproperty('value-widget', object)
    gproperty('units-widget', object)
    gproperty('helper', object)
    
    def __init__(self, pid, index=0, units='Metric',
                       active_widget=None, name_widget=None,
                       value_widget=None, units_widget=None,
                       helper=None):
        GObject.__init__(self)
        PropertyObject.__init__(self, active_widget=active_widget,
                                      name_widget=name_widget,
                                      value_widget=value_widget,
                                      units_widget=units_widget,
                                      unit_standard=units,
                                      helper=helper)
        SensorProxyMixin.__init__(self, pid, index)
        
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
        self.connect('notify::unit-standard', self._notify_unit_standard_cb)
        self.connect('notify::supported', self._notify_supported_cb)
        self.connect('notify::active', self._notify_active_cb)
        self._update_view()
        self._sensitize_widgets()
    
    def prop_get_sensor(self):
        return self._sensor
        
    def _notify_active_cb(self, o, pspec):
        if self._toggleable:
            self.active_widget.set_active(self.active)
        self._sensitize_widgets()
        if not self.active:
            self._sensor.clear()
        self.emit('active-changed', self.active)
        
    def _active_toggled_cb(self, togglebutton):
        self.active = togglebutton.get_active()
    
    
    def _active_clicked_cb(self, button):
        self.active = not self.active
        
        
    def  _notify_unit_standard_cb(self, o, pspec):
        self._update_view()
                
    def  _notify_supported_cb(self, o, pspec):
        if not self.supported:
            self.active = False
        self._sensitize_widgets()
    
     
    def _sensitize_widgets(self):
        if self.active_widget:
            self.active_widget.set_sensitive(self.supported)
        for widget in (self.name_widget, self.value_widget, self.units_widget):
            if widget:
                widget.set_sensitive(self.supported and self.active)
            
            
    def _sensor_data_changed_cb(self, sensor, data):
        self._update_view()
       
       
    def _update_view(self):
        if self.unit_standard == 'Imperial':
            value = self._sensor.imperial_value
            units = self._sensor.imperial_units
        else:
            value = self._sensor.metric_value
            units = self._sensor.metric_units
        if not units: units=''
        if not value: value=''
        if self.helper and callable(self.helper):
            self.helper(self)
        else:    
            if self.name_widget:
                self.name_widget.set_text(self._sensor.name)
            if self.value_widget:
                self.value_widget.set_text(value)
            if self.units_widget:
                self.units_widget.set_text(units)

        
(PID, INDEX, ONE_SHOT, HELPER, LABEL, BUTTON, ENTRY, UNIT) = range (8)     

SENSORS= [
        ('0101', 0, False, None,
         'dtc_label', None, 'dtc_entry', None),
        ('0104', 0, False, None, 
         None, 'load_button', 'load_entry', 'load_unit_label'),
        ('0105', 0, False, None, 
         None, 'coolant_button', 'coolant_entry', 'coolant_unit_label'),
        ('010C', 0, False, None, 
         None, 'rpm_button', 'rpm_entry', 'rpm_unit_label'),
        ('010D', 0, False, None, 
         None, 'speed_button', 'speed_entry', 'speed_unit_label'),
        ('0111', 0, False, None, 
         None, 'throttle_button', 'throttle_entry', 'throttle_unit_label'),
        ('010E', 0, False, None, 
         None, 'timing_button', 'timing_entry', 'timing_unit_label'),
        ('010B', 0, False, None, 
         None, 'intake_pres_button', 'intake_pres_entry', 'intake_pres_unit_label'),
        ('010F', 0, False, None, 
         None, 'air_temp_button', 'air_temp_entry', 'air_temp_unit_label'),
        ('0110', 0, False, None, 
         None, 'air_flow_button', 'air_flow_entry', 'air_flow_unit_label'),
        ('0103', 0, False, None, 
         None, 'fuel_status_button', 'fuel_status1_entry', None),
        ('0103', 1, False, None, 
         None, 'fuel_status_button', 'fuel_status2_entry', None),
        ('0106', 0, False, None, 
         None, 'fuel_trim_short1_button', 'fuel_trim_short1_entry', 'fuel_trim_short1_unit_label'),
        ('0107', 0, False, None, 
         None, 'fuel_trim_long1_button', 'fuel_trim_long1_entry', 'fuel_trim_long1_unit_label'),
        ('0108', 0, False, None, 
         None, 'fuel_trim_short2_button', 'fuel_trim_short2_entry', 'fuel_trim_short2_unit_label'),
        ('0109', 0, False, None, 
         None, 'fuel_trim_long2_button', 'fuel_trim_long2_entry', 'fuel_trim_long2_unit_label'),
        ('010A', 0, False, None, 
         None, 'fuel_pressure_button', 'fuel_pressure_entry', 'fuel_pressure_unit_label'),
        ('0112', 0, False, None, 
         None, 'sec_air_status_button', 'sec_air_status_entry', None),
        ('011C', 0, True, None, 
         'designation_label', None, 'designation_entry', None)
        ]

  
        
        
if __name__ == '__main__':

    def switch_units(s):
        if s.unit_standard == 'Metric':
            s.unit_standard = 'Imperial'
        else:
            s.unit_standard = 'Metric'
        return True
        
    def switch_data(s):
        print 'in switch_data'
        if s._sensor.data == '1':
            s._sensor.data = '2'
        else:
            s._sensor.data = '1'
        return True
          
    w = gtk.Window()
    w.connect('destroy', lambda w: gtk.main_quit())
    tog = gtk.ToggleButton()
    nam = gtk.Entry()
    un = gtk.Label()
    val = gtk.Entry()
    vbox = gtk.VBox()
    vbox.pack_start(tog)
    vbox.pack_start(nam)
    vbox.pack_start(val)
    vbox.pack_start(un)
    w.add(vbox)
    
    s = LiveDataView('0103', active_widget=tog,
                               name_widget=nam,
                               value_widget=val,
                               units_widget=un)
    #print 'pid: %s' % s.pid
    #print 'index: %s' % s.index
    #print 'name: %s' % s.name
    w.show_all()
    s.supported = True
    #s.active = True
    s.units = 'Imperial'
    s._sensor.data = '1'
    id = gobject.timeout_add(500, switch_units, s)
    id = gobject.timeout_add(1000, switch_data, s)
    
    gtk.main()
    
    
    
    
