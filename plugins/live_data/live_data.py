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
from garmon.obd_device import OBDDataError, OBDPortError
from garmon.sensor import StateMixin, UnitMixin
from garmon.sensor import Command, Sensor
from garmon.widgets import MILWidget, SensorView, CommandView


__name = _('Live Data')
__version = '0.1'
__author = 'Ben Van Mechelen'
__description = _('View the most imported live data like:\n *Fuel System\n *Intake\n *VIN\n *...\n')
__class = 'LiveData'


class LiveData (gtk.VBox, Plugin):
    __gtype_name__='LiveData'
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
        mil.connect('active-changed', self._view_active_changed_cb)
        xml.get_widget('mil_alignment').add(mil)
        mil.show()
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
            
            view = SensorView(pid, index, units=self._unit_standard,
                       active_widget=button, name_widget=label,
                       value_widget=entry, units_widget=unit,
                       helper=func)
                       
            view.connect('active-changed', self._view_active_changed_cb)
            
            if item[ONE_SHOT]:
                self.os_views.append(view)
            else:
                self.views.append(view)

        
        for item in COMMANDS: 
            label = button = entry = None
            command = item[COMMAND]
            name = item[NAME]
            if item[LABEL]:
                label = xml.get_widget(item[LABEL])
            if item[BUTTON]:
                button = xml.get_widget(item[BUTTON])
            if item[ENTRY]:
                entry = xml.get_widget(item[ENTRY])
            func = (item[HELPER])
            
            view = CommandView(command=command, name=name, 
                               active_widget=button, name_widget=label,
                               value_widget=entry, helper=func)
                       
            view.connect('active-changed', self._view_active_changed_cb)
            
            if item[ONE_SHOT]:
                self.os_views.append(view)
            else:
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
        for views in (self.views, self.os_views):
            for view in views:
                if self.app.device:
                    if view.command.command in self.app.device.supported_commands:
                        view.supported=True
                        if view in self.os_views or view.command.command == '0101':
                            view.active=True
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
        for view in self.os_views:
            if view.active:
                self.app.scheduler.add(view.command, True)
        self.status = STATUS_WORKING
        
            
    def stop(self):
        if self.status == STATUS_STOP:
            return
        for views in (self.views, self.os_views):
            for view in views:
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
        
        for views in (self.views, self.os_views):
            for view in views:
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
            self.app.device.disconnect(cb_id)



        
(COMMAND, NAME) = range(2)
        
(PID, INDEX, ONE_SHOT, HELPER, LABEL, BUTTON, ENTRY, UNIT) = range (8)     

COMMANDS = [
            ('voltage', _('Voltage'), False, None,
                 None, 'voltage_button', 'voltage_entry'),
            ('protocol', _('Protocol'), True, None,
                 'protocol_label', None, 'protocol_entry'),
           ]
              
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
         'designation_label', None, 'designation_entry', None),
        ('0114', 0, False, None, 
         None, 'sensor11_button', 'sensor11_volt_entry', 'sensor11_volt_unit_label'),
        ('0114', 1, False, None, 
         None, 'sensor11_button', 'sensor11_trim_entry', 'sensor11_trim_unit_label'),
        ('0115', 0, False, None, 
         None, 'sensor12_button', 'sensor12_volt_entry', 'sensor12_volt_unit_label'),
        ('0115', 1, False, None, 
         None, 'sensor12_button', 'sensor12_trim_entry', 'sensor12_trim_unit_label'),
        ('0116', 0, False, None, 
         None, 'sensor13_button', 'sensor13_volt_entry', 'sensor13_volt_unit_label'),
        ('0116', 1, False, None, 
         None, 'sensor13_button', 'sensor13_trim_entry', 'sensor13_trim_unit_label'),
        ('0117', 0, False, None, 
         None, 'sensor14_button', 'sensor14_volt_entry', 'sensor14_volt_unit_label'),
        ('0117', 1, False, None, 
         None, 'sensor14_button', 'sensor14_trim_entry', 'sensor14_trim_unit_label'),
        ('0118', 0, False, None, 
         None, 'sensor21_button', 'sensor21_volt_entry', 'sensor21_volt_unit_label'),
        ('0118', 1, False, None, 
         None, 'sensor21_button', 'sensor21_trim_entry', 'sensor21_trim_unit_label'),
        ('0119', 0, False, None, 
         None, 'sensor22_button', 'sensor22_volt_entry', 'sensor22_volt_unit_label'),
        ('0119', 1, False, None, 
         None, 'sensor22_button', 'sensor22_trim_entry', 'sensor22_trim_unit_label'),
        ('011A', 0, False, None, 
         None, 'sensor23_button', 'sensor23_volt_entry', 'sensor23_volt_unit_label'),
        ('011A', 1, False, None, 
         None, 'sensor23_button', 'sensor23_trim_entry', 'sensor23_trim_unit_label'),
        ('011B', 0, False, None, 
         None, 'sensor24_button', 'sensor24_volt_entry', 'sensor24_volt_unit_label'),
        ('011B', 1, False, None, 
         None, 'sensor24_button', 'sensor24_trim_entry', 'sensor24_trim_unit_label'),
        ]

   
    
