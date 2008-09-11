#!/usr/bin/python
#
# o2_sensors.py
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
from garmon.obd_device import OBDDataError, OBDPortError
from garmon.sensor import StateMixin, UnitMixin
from garmon.sensor import Command, Sensor
from garmon.widgets import MILWidget, SensorView


__name = _('02 Sensors')
__version = '0.1'
__author = 'Ben Van Mechelen'
__description = _('Displays O2 sensor data as well as engine RPM')
__class = 'O2SensorsData'


class O2SensorsData (gtk.VBox, Plugin):
    __gtype_name__='O2SensorsData'
    def __init__ (self, app):
        gtk.VBox.__init__(self)
        Plugin.__init__(self)

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

        self._obd_cbs.append(app.device.connect('connected', 
                                             self._device_connected_cb))
        self._notebook_cbs.append(app.notebook.connect('switch-page', 
                                                  self._notebook_page_change_cb))
        
        self._scheduler_cbs.append(self.app.scheduler.connect('notify::working',
                                             self._scheduler_notify_working_cb))
        
        self._device_connected_cb(app.device)
        
    
    def _setup_gui(self):
        dirname = os.path.dirname(__file__)
        filename = os.path.join(dirname, 'o2_sensors.glade')
        self.glade_xml = glade.XML(filename, 'main_hbox')
        main_hbox = self.glade_xml.get_widget('main_hbox')
        self.pack_start(main_hbox)
        main_hbox.show_all()
        self.show_all()
        
        
    def _setup_sensors(self):

        self.views = []
        self.os_views = []

        xml = self.glade_xml
               
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
            
            view = SensorView(pid, index, units=self._unit_standard,
                       active_widget=button, name_widget=label,
                       value_widget=entry, units_widget=unit,
                       helper=func)
                       
            view.connect('active-changed', self._view_active_changed_cb)
            
            self.views.append(view)

        
    def _scheduler_notify_working_cb(self, scheduler, pspec):
        if not scheduler.working:
            for views in (self.views, self.os_views):
                for view in views:
                    view.command.clear()
        else:
            for view in self.os_views:
                if view.active:
                    self.app.scheduler.add(view.command, True)
                    
            
    def _view_active_changed_cb(self, view, active):
        if active:
            if self.status == STATUS_WORKING:
                self.app.scheduler.add(view.command)
        else:
            self.app.scheduler.remove(view.command)
    
    
    def _update_supported_views(self):
        print 'in update_supported_views'
        for view in self.views:
            if self.app.device:
                if view.command.command in self.app.device.supported_commands:
                    view.supported=True
                    #view.active=True
                else:
                    view.supported=False
            else:
                view.supported=False
   
            
    def start(self):
        if self.status == STATUS_WORKING:
            return
        for view in self.views:
            if view.active:
                self.app.scheduler.add(view.command, False)
        self.status = STATUS_WORKING
        
            
    def stop(self):
        if self.status == STATUS_STOP:
            return
        for view in self.views:
            self.app.scheduler.remove(view.command)
            view.command.clear()
        self.status = STATUS_STOP
        
        
    def _device_connected_cb(self, device, connected=False):
        page = self.app.notebook.get_current_page()
        visible = self.app.notebook.get_nth_page(page) is self
        self.stop()
        self._update_supported_views()
        if visible:
            self.start()


    def _notify_units_cb(self, pname, pvalue, ptype, args):
        if pname == 'imperial' and pvalue:
            self._unit_standard = 'Imperial'
        else:
            self._unit_standard = 'Metric'
        
        for views in self.views:
            view.unit_standard = self._unit_standard
            
            
    def _notebook_page_change_cb (self, notebook, no_use, page):
        plugin = notebook.get_nth_page(page)
        if plugin is self:
            self.start()
        else:
            self.stop()
            
    def load(self):
        self.app.notebook.append_page(self, gtk.Label(_('O2 Sensors')))            
            
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
            self.app.device.disconnect(cb_id)




        
(PID, INDEX, HELPER, LABEL, BUTTON, ENTRY, UNIT) = range (7)     
              
SENSORS= [
        ('0104', 0, None, 
         None, 'load_button', 'load_entry', 'load_unit_label'),
        ('010C', 0, None, 
         None, 'rpm_button', 'rpm_entry', 'rpm_unit_label'),
        ('0111', 0, None, 
         None, 'throttle_button', 'throttle_entry', 'throttle_unit_label'),
        ('010E', 0, None, 
         None, 'timing_button', 'timing_entry', 'timing_unit_label'),
        ('010A', 0, None, 
         None, 'fuel_pressure_button', 'fuel_pressure_entry', 'fuel_pressure_unit_label'),
        ('0110', 0, None, 
         None, 'air_flow_button', 'air_flow_entry', 'air_flow_unit_label'),
        ('0114', 0, None, 
         None, 'sensor11_button', 'sensor11_volt_entry', 'sensor11_volt_unit_label'),
        ('0114', 1, None, 
         None, 'sensor11_button', 'sensor11_trim_entry', 'sensor11_trim_unit_label'),
        ('0115', 0, None, 
         None, 'sensor12_button', 'sensor12_volt_entry', 'sensor12_volt_unit_label'),
        ('0115', 1, None, 
         None, 'sensor12_button', 'sensor12_trim_entry', 'sensor12_trim_unit_label'),
        ('0116', 0, None, 
         None, 'sensor13_button', 'sensor13_volt_entry', 'sensor13_volt_unit_label'),
        ('0116', 1, None, 
         None, 'sensor13_button', 'sensor13_trim_entry', 'sensor13_trim_unit_label'),
        ('0117', 0, None, 
         None, 'sensor14_button', 'sensor14_volt_entry', 'sensor14_volt_unit_label'),
        ('0117', 1, None, 
         None, 'sensor14_button', 'sensor14_trim_entry', 'sensor14_trim_unit_label'),
        ('0118', 0, None, 
         None, 'sensor21_button', 'sensor21_volt_entry', 'sensor21_volt_unit_label'),
        ('0118', 1, None, 
         None, 'sensor21_button', 'sensor21_trim_entry', 'sensor21_trim_unit_label'),
        ('0119', 0, None, 
         None, 'sensor22_button', 'sensor22_volt_entry', 'sensor22_volt_unit_label'),
        ('0119', 1, None, 
         None, 'sensor22_button', 'sensor22_trim_entry', 'sensor22_trim_unit_label'),
        ('011A', 0, None, 
         None, 'sensor23_button', 'sensor23_volt_entry', 'sensor23_volt_unit_label'),
        ('011A', 1, None, 
         None, 'sensor23_button', 'sensor23_trim_entry', 'sensor23_trim_unit_label'),
        ('011B', 0, None, 
         None, 'sensor24_button', 'sensor24_volt_entry', 'sensor24_volt_unit_label'),
        ('011B', 1, None, 
         None, 'sensor24_button', 'sensor24_trim_entry', 'sensor24_trim_unit_label'),
        ]
