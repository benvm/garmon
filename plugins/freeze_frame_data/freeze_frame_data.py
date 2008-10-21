#!/usr/bin/python
#
# freeze_frame_data.p
#
# Copyright (C) Ben Van Mechelen 2008 <me@benvm.be>
# 
# freeze_frame_data.py is free software; you can redistribute it and/or modify
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
from garmon.sensor import decode_dtc_code
from garmon.widgets import SensorView, SensorProgressView


__name = _('Freeze Frame Data')
__version = '0.2'
__author = 'Ben Van Mechelen'
__description = _('View Freeze Frame data associated with a certain dtc\n\nEXPERIMENTAL')
__class = 'FreezeFrameData'


class FreezeFrameData (gtk.VBox, Plugin):
    __gtype_name__='FreezeFrameData'
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
        filename = os.path.join(dirname, 'freeze_frame_data.glade')
        self.glade_xml = glade.XML(filename, 'main_hbox')
        main_hbox = self.glade_xml.get_widget('main_hbox')
        self.pack_start(main_hbox)
        main_hbox.show_all()
        self.show_all()
        
        button = self.glade_xml.get_widget('re-read-button')
        button.connect('clicked', self._reread_button_clicked)
        
        
    def _setup_sensors(self):

        self.views = []

        xml = self.glade_xml
               
        for item in SENSORS: 
            label = entry = unit = None
            pid = item[PID]
            index = item[INDEX]
            if item[LABEL]:
                label = xml.get_widget(item[LABEL])
            if item[ENTRY]:
                entry = xml.get_widget(item[ENTRY])
            if item[UNIT]:
                unit = xml.get_widget(item[UNIT])
            func = (item[HELPER])
            
            view = SensorView(pid, index, units=self._unit_standard,
                       name_widget=label, value_widget=entry, 
                       units_widget=unit, helper=func)
            
            self.views.append(view)

        for item in PROGRESS: 
            label = bar = None
            pid = item[PID]
            index = item[INDEX]
            if item[LABEL]:
                label = xml.get_widget(item[LABEL])
            if item[BAR]:
                bar = xml.get_widget(item[BAR])
            func = (item[HELPER])
            
            view = SensorProgressView(pid, index,
                       name_widget=label,
                       progress_widget=bar, helper=func)
            
            self.views.append(view)


    def _reread_button_clicked(self, button):
        self._update_supported_views()
        self.start()

    
    def _scheduler_notify_working_cb(self, scheduler, pspec):
        pass
                       
    
    def _update_supported_views(self):
        print 'in update_supported_views'
        if self.app.device.supported_freeze_frame_pids == None:
            print 'supported_freeze_frame_pids not yet read'
            return
        for view in self.views:
            if self.app.device:
                if view.command.command in self.app.device.supported_freeze_frame_pids:
                    view.supported=True
                    view.active=True
                else:
                    view.supported=False
                    view.active=False
            else:
                view.supported=False
                view.active=False
   
            
    def start(self):
        for view in self.views:
            if view.supported:
                self.app.scheduler.add(view.command, True)
        self.app.scheduler.working = True
        
            
    def stop(self):
        pass
        
        
    def _device_connected_cb(self, device, connected=False):
        page = self.app.notebook.get_current_page()
        visible = self.app.notebook.get_nth_page(page) is self
        self._update_supported_views()
        if visible:
            self.app.device.read_supported_freeze_frame_pids()


    def _notify_units_cb(self, pname, pvalue, ptype, args):
        if pname == 'imperial' and pvalue:
            self._unit_standard = 'Imperial'
        else:
            self._unit_standard = 'Metric'
        
        for view in self.views:
            view.unit_standard = self._unit_standard
            
            
    def _notebook_page_change_cb (self, notebook, no_use, page):
        plugin = notebook.get_nth_page(page)
        if plugin is self:
            self.start()

            
    def load(self):
        self.app.notebook.append_page(self, gtk.Label(_('Freeze Frame Data')))            
            
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


def _dtc_code_helper(view):
    dtc = decode_dtc_code(view.command.metric_value)
    if not dtc:
        dtc = ''
    view.value_widget.set_text(dtc)

        
(COMMAND, NAME) = range(2)

(PID, INDEX, HELPER, LABEL, ENTRY, UNIT) = range (6)
BAR = 4

SENSORS= [
        ('0202', 0, _dtc_code_helper,
         None, 'dtc_entry', None),
        ('0204', 0, None, 
         'load_label', 'load_entry', 'load_unit_label'),
        ('0205', 0, None, 
         'coolant_label', 'coolant_entry', 'coolant_unit_label'),
        ('020C', 0, None, 
         'rpm_label', 'rpm_entry', 'rpm_unit_label'),
        ('020D', 0, None, 
         'speed_label', 'speed_entry', 'speed_unit_label'),
        ('0211', 0, None, 
         'throttle_label', 'throttle_entry', 'throttle_unit_label'),
        ('020E', 0, None, 
         'timing_label', 'timing_entry', 'timing_unit_label'),
        ('020B', 0, None, 
         'intake_pres_label', 'intake_pres_entry', 'intake_pres_unit_label'),
        ('020F', 0, None, 
         'air_temp_label', 'air_temp_entry', 'air_temp_unit_label'),
        ('0210', 0, None, 
         'air_flow_label', 'air_flow_entry', 'air_flow_unit_label'),
        ('0203', 0, None, 
         'fuel_status1_label', 'fuel_status1_entry', None),
        ('0203', 1, None, 
         'fuel_status2_label', 'fuel_status2_entry', None),
        ('0206', 0, None, 
         'fuel_trim_short1_label', 'fuel_trim_short1_entry', 'fuel_trim_short1_unit_label'),
        ('0207', 0, None, 
         'fuel_trim_long1_label', 'fuel_trim_long1_entry', 'fuel_trim_long1_unit_label'),
        ('0208', 0, None, 
         'fuel_trim_short2_label', 'fuel_trim_short2_entry', 'fuel_trim_short2_unit_label'),
        ('0209', 0, None, 
         'fuel_trim_long2_label', 'fuel_trim_long2_entry', 'fuel_trim_long2_unit_label'),
        ('020A', 0, None, 
         'fuel_pressure_label', 'fuel_pressure_entry', 'fuel_pressure_unit_label'),
        ('0212', 0, None, 
         'sec_air_status_label', 'sec_air_status_entry', None),
        ('0214', 0, None, 
         'sensor11_label', 'sensor11_volt_entry', 'sensor11_volt_unit_label'),
        ('0214', 1, None, 
         'sensor11_label', 'sensor11_trim_entry', 'sensor11_trim_unit_label'),
        ('0215', 0, None, 
         'sensor12_label', 'sensor12_volt_entry', 'sensor12_volt_unit_label'),
        ('0215', 1, None, 
         'sensor12_label', 'sensor12_trim_entry', 'sensor12_trim_unit_label'),
        ('0216', 0, None, 
         'sensor13_label', 'sensor13_volt_entry', 'sensor13_volt_unit_label'),
        ('0216', 1, None, 
         'sensor13_label', 'sensor13_trim_entry', 'sensor13_trim_unit_label'),
        ('0217', 0, None, 
         'sensor14_label', 'sensor14_volt_entry', 'sensor14_volt_unit_label'),
        ('0217', 1, None, 
         'sensor14_label', 'sensor14_trim_entry', 'sensor14_trim_unit_label'),
        ('0218', 0, None, 
         'sensor21_label', 'sensor21_volt_entry', 'sensor21_volt_unit_label'),
        ('0218', 1, None, 
         'sensor21_label', 'sensor21_trim_entry', 'sensor21_trim_unit_label'),
        ('0219', 0, None, 
         'sensor22_label', 'sensor22_volt_entry', 'sensor22_volt_unit_label'),
        ('0219', 1, None, 
         'sensor22_label', 'sensor22_trim_entry', 'sensor22_trim_unit_label'),
        ('021A', 0, None, 
         'sensor23_label', 'sensor23_volt_entry', 'sensor23_volt_unit_label'),
        ('021A', 1, None, 
         'sensor23_label', 'sensor23_trim_entry', 'sensor23_trim_unit_label'),
        ('021B', 0, None, 
         'sensor24_label', 'sensor24_volt_entry', 'sensor24_volt_unit_label'),
        ('021B', 1, None, 
         'sensor24_label', 'sensor24_trim_entry', 'sensor24_trim_unit_label'),
        ('022C', 0, None, 
         'egr_label', 'egr_entry', 'egr_unit_label'),
        ('022D', 0, None, 
         'egr_error_label', 'egr_error_entry', 'egr_error_unit_label'),
        ]  
    
    
PROGRESS = [
            ('0214', 1, None, 
             'sensor11_label', 'sensor11_bar'),
            ('0215', 1, None, 
             'sensor12_label', 'sensor12_bar'),
            ('0216', 1, None, 
             'sensor13_label', 'sensor13_bar'),
            ('0217', 1, None, 
             'sensor14_label', 'sensor14_bar'),
            ('0218', 1, None, 
             'sensor21_label', 'sensor21_bar'),
            ('0219', 1, None, 
             'sensor22_label', 'sensor22_bar'),
            ('021A', 1, None, 
             'sensor23_label', 'sensor23_bar'),
            ('021B', 1, None, 
             'sensor24_label', 'sensor24_bar'),
            ('0206', 0, None, 
             'fuel_trim_short1_label', 'fuel_trim_short1_bar'),
            ('0207', 0, None, 
             'fuel_trim_long1_label', 'fuel_trim_long1_bar'),
            ('0208', 0, None, 
             'fuel_trim_short2_label', 'fuel_trim_short2_bar'),
            ('0209', 0, None, 
             'fuel_trim_long2_label', 'fuel_trim_long2_bar'),
           ]
