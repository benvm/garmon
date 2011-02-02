#!/usr/bin/python
#
# freeze_frame_data.p
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


import os
from gettext import gettext as _

import gobject
from gobject import GObject
import gtk

import garmon
import garmon.plugin
import garmon.sensor as sensor

from garmon import logger
from garmon.property_object import PropertyObject, gproperty, gsignal
from garmon.plugin import Plugin, STATUS_STOP, STATUS_WORKING, STATUS_PAUSE
from garmon.obd_device import OBDDataError, OBDPortError
from garmon.sensor import StateMixin, UnitMixin
from garmon.sensor import Command, Sensor
from garmon.sensor import decode_dtc_code
from garmon.widgets import SensorView, SensorProgressView


__name = _('Freeze Frame Data')
__version = garmon.GARMON_VERSION
__author = 'Ben Van Mechelen'
__description = _('View Freeze Frame data associated with a certain dtc\n\nEXPERIMENTAL')
__class = 'FreezeFramePlugin'



class FreezeFrame (GObject, PropertyObject):
    __gtype_name__ = 'FreezeFrame'

    gproperty('widget', object, flags=gobject.PARAM_READABLE)
    gproperty('frame', str, flags=gobject.PARAM_READABLE)

    def prop_get_widget(self):
        return self._main_hbox

    def prop_get_frame(self):
        return self._frame
    
        
    def __init__(self, plugin, frame):
        GObject.__init__(self)
        PropertyObject.__init__(self)

        self.plugin = plugin 
        self._frame = frame
		
        self._pref_cbs = []
        self._app_cbs = []
        self._notebook_cbs = []
        self._queue_cbs = []
        self._obd_cbs = []
        
        if plugin.app.prefs.get('imperial', False):
            self._unit_standard = 'Imperial'
        else:
            self._unit_standard = 'Metric'
            
        cb_id = plugin.app.prefs.add_watch('imperial', 
                                    self._notify_units_cb)
        self._pref_cbs.append(('imperial', cb_id))
        
        self._setup_gui()
        self._setup_sensors()
        self._get_supported_pids()

		
    def _setup_gui(self):
        dirname = os.path.dirname(__file__)
        filename = os.path.join(dirname, 'freeze_frame_data.ui')
        self._builder = gtk.Builder()
        self._builder.set_translation_domain('garmon')
        self._builder.add_from_file(filename)
        
        self._main_hbox = self._builder.get_object('main_hbox')
        self._main_hbox.show_all()
        
        self._read_button = self._builder.get_object('read-button')
        self._read_button.connect('clicked', self._read_button_clicked)
        
        
    def _setup_sensors(self):

        self._views = []

        for item in SENSORS: 
            label = entry = unit = None
            pid = item[PID] + '%0*d' % (2, int(self._frame))
            index = item[INDEX]
            if item[LABEL]:
                label = self._builder.get_object(item[LABEL])
            if item[ENTRY]:
                entry = self._builder.get_object(item[ENTRY])
            if item[UNIT]:
                unit = self._builder.get_object(item[UNIT])
            func = (item[HELPER])
            
            view = SensorView(pid, index, units=self._unit_standard,
                       name_widget=label, value_widget=entry, 
                       units_widget=unit, helper=func)
            
            self._views.append(view)

        for item in PROGRESS: 
            label = bar = None
            pid = item[PID] + '%0*d' % (2, int(self._frame))
            index = item[INDEX]
            if item[LABEL]:
                label = self._builder.get_object(item[LABEL])
            if item[BAR]:
                bar = self._builder.get_object(item[BAR])
            func = (item[HELPER])
            
            view = SensorProgressView(pid, index,
                       name_widget=label,
                       progress_widget=bar, helper=func)
            
            self._views.append(view)				


    def _get_supported_pids(self):

        def data_changed_cb(cmd, pspec):
            offset = int(cmd.command[2:4])
            self._supported_pids += decode_pids_from_bitstring(cmd.data, offset, self._frame)
            next = '%d' % (offset + 20)
            if '02' + next in self._supported_pids:
                command = Command('02' + next + self._frame)
                command.connect('notify::data', data_changed_cb)
                self.plugin.app.queue.add(command, True)
            else:
                self._update_supported_views()

        def error_cb(cmd, msg, args):
            logger.error('error reading supported pids, msg is: %s' % msg)
            raise OBDPortError('OpenPortFailed', 
                               _('could not read supported pids\n\n' + msg))

        self._supported_pids = []
        command = Command('0200' + self._frame)
        command.connect('notify::data', data_changed_cb)
        self.plugin.app.queue.add(command, True)

           
    def _update_supported_views(self):
        logger.debug('in update_supported_views')
        for view in self._views:
            if view.command.command in self._supported_pids:
                view.supported=True
                view.active=True
            else:
                view.supported=False
                view.active=False

                
    def _notify_units_cb(self, pname, pvalue, args):
        if pname == 'imperial' and pvalue:
            self._unit_standard = 'Imperial'
        else:
            self._unit_standard = 'Metric'
        
        for view in self.views:
            view.unit_standard = self._unit_standard

            
    def _read_button_clicked(self, button):
        self.update()


    def update(self):
        logger.debug('entering FreezeFrame.update')
        for view in self._views:
            if view.supported:
                self.plugin.app.queue.add(view.command, True)
        self.plugin.app.queue.start()

    
	def unload(self):
		self.app.notebook.remove(self)
        for name, cb_id in self._pref_cbs:
            self.plugin.app.prefs.remove_watch(name, cb_id)
        for cb_id in self._app_cbs:
            self.plugin.app.disconnect(cb_id)
        for cb_id in self._notebook_cbs:
            self.plugin.app.notebook.disconnect(cb_id)
        for cb_id in self._queue_cbs:
            self.plugin.app.queue.disconnect(cb_id)
        for cb_id in self._obd_cbs:
            self.plugin.app.device.disconnect(cb_id)			


		
class FreezeFramePlugin (Plugin, PropertyObject):
    __gtype_name__ = 'FreezeFramePlugin'


    gproperty('widget', object, flags=gobject.PARAM_READABLE)

    def prop_get_widget(self):
        return self._main_box

    
    def __init__(self, app):
        Plugin.__init__(self)
        PropertyObject.__init__(self)

        self.app = app
	
        self._pref_cbs = []
        self._app_cbs = []
        self._notebook_cbs = []
        self._queue_cbs = []
        self._obd_cbs = []

        self._command = Command('0901')
        self._command.connect('notify::data', self._command_data_changed)
        
        self.status = STATUS_STOP

        self._frames = []

        self._setup_gui()
		
        self._obd_cbs.append(app.device.connect('supported-pids-changed', 
                                             self._supported_pids_changed_cb))
        self._notebook_cbs.append(app.notebook.connect('switch-page', 
                                                  self._notebook_page_change_cb))

                                                  
    def _setup_gui (self):
        self._main_box = gtk.HBox()
        self._frames_notebook = gtk.Notebook()
        self._main_box.pack_start(self._frames_notebook)
        self._main_box.show_all()


    def _command_data_changed(self, command, pspec):
        logger.debug('entering FreezeFramePlugin._command_data_changed')
        self.app.queue.remove(self._command)
        for item in range(len(self._frames) + 1, int(command.data) + 1):
            frame = FreezeFrame(self, '%0*d' % (2, item))
            self._frames_notebook.append_page(frame.widget, 
                                        gtk.Label(_('Frame %s') % frame.frame))
            self._frames.append(frame)


    def _supported_pids_changed_cb(self, device):
        logger.debug('entering FreezeFramePlugin._supported_pids_changed_cb')
        page = self.app.notebook.get_current_page()
        if self.app.notebook.get_nth_page(page) is self._main_box:
            if self._command.command in self.app.device.supported_pids:
                self.app.queue.add(self._command)
            self.app.queue.start()

    
    def _notebook_page_change_cb (self, notebook, no_use, page):
        widget = notebook.get_nth_page(page)
        if widget is self._main_box:
            if self._command.command in self.app.device.supported_pids:
                self.app.queue.add(self._command)

            
    def load(self):
        self.app.notebook.append_page(self._main_box, gtk.Label(_('Freeze Frame Data')))            

		
    def unload(self):
        self.app.notebook.remove(self._main_box)
        for frame in self._frames:
            frame.unload()
        for name, cb_id in self._pref_cbs:
            self.app.prefs.remove_watch(name, cb_id)
        for cb_id in self._app_cbs:
            self.app.disconnect(cb_id)
        for cb_id in self._notebook_cbs:
            self.app.notebook.disconnect(cb_id)
        for cb_id in self._queue_cbs:
            self.app.queue.disconnect(cb_id)
        for cb_id in self._obd_cbs:
            self.app.device.disconnect(cb_id)



def _dtc_code_helper(view):
    dtc = decode_dtc_code(view.command.metric_value)
    if not dtc:
        dtc = ''
    view.value_widget.set_text(dtc)



def decode_pids_from_bitstring(data, offset, suffix):
    logger.debug('entering decode_pids_from_bitstring')
    pids = []
    for item in data:
        bitstr = sensor.hex_to_bitstr(item)
        for i, bit in enumerate(bitstr):
            if bit == "1":
                pid = i + 1 + offset
                if pid < 16: 
                    pid_str = '020' + hex(pid)[2:] + suffix
                else:
                    pid_str = '02' + hex(pid)[2:] + suffix
                pids.append(pid_str.upper())
    return pids

        
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
