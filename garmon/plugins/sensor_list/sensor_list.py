#!/usr/bin/python
#
# sensorlist.py
#
# Copyright (C) Ben Van Mechelen 2007 <me@benvm.be>
# 
# sensors_page.py is free software; you can redistribute it and/or modify
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

import gobject
import gtk

import garmon
import garmon.plugin
from garmon.plugin import Plugin, STATUS_STOP, STATUS_WORKING, STATUS_PAUSE
from garmon.obd_device import OBDDataError, OBDPortError 
import garmon.sensor
from garmon.sensor import METRIC, IMPERIAL, NAME, SENSORS


__name = _('Sensor List')
__version = '0.1'
__author = 'Ben Van Mechelen'
__description = _('A list of all supported sensors')
__class = 'SensorList'


(
    COLUMN_ACTIVE,
    COLUMN_PID,
    COLUMN_NUM,
    COLUMN_DESCRIPTION,
    COLUMN_VALUE,
    COLUMN_UNIT
) = range(6)



class SensorList (Plugin):

    def __init__ (self, garmon):
        Plugin.__init__(self)
        
        self.garmon = garmon
        self.units = garmon.units
        
        self._timeout_id = None
        self.status = STATUS_STOP
        self.pids = []
        
        self.scrol_win = gtk.ScrolledWindow()
        self.scrol_win.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scrol_win.set_border_width(5)
        self.pack_start(self.scrol_win)
        
        self.treemodel = self._create_treemodel()
        self.treeview = gtk.TreeView(self.treemodel)
        self.treeview.set_rules_hint(True)
        
        self._add_columns()
        
        self.scrol_win.add(self.treeview)
        
        self.show_all()
        
        garmon.connect("reset", self._on_reset)
        garmon.connect("units-change", self._on_units_changed)
        garmon.connect('page-changed', self._on_page_changed)
        
        
    def _create_treemodel(self):

        tree_store = gtk.TreeStore(
            gobject.TYPE_BOOLEAN,
            gobject.TYPE_STRING,
            gobject.TYPE_INT,
            gobject.TYPE_STRING,
            gobject.TYPE_STRING,
            gobject.TYPE_STRING)
            
        return tree_store
        
        
    def _add_columns(self):
        model = self.treemodel

        # column for active toggles
        renderer = gtk.CellRendererToggle()
        renderer.connect('toggled', self._pid_active_toggled, model)

        column = gtk.TreeViewColumn(None, renderer, active=COLUMN_ACTIVE)
        self.treeview.append_column(column)

        # column for PIDs
        column = gtk.TreeViewColumn(_('PID'), gtk.CellRendererText(),
                                    text=COLUMN_PID)
        #column.set_sort_column_id(COLUMN_PID)
        self.treeview.append_column(column)

        # column for value number of a PID with more then one value
        column = gtk.TreeViewColumn('#', gtk.CellRendererText(),
                                    text=COLUMN_NUM, visible=COLUMN_NUM)
        self.treeview.append_column(column)
        
        # columns for descriptions
        column = gtk.TreeViewColumn(_('Description'), gtk.CellRendererText(),
                                    text=COLUMN_DESCRIPTION)
        #column.set_sort_column_id(COLUMN_DESCRIPTION)
        self.treeview.append_column(column)

        # column for values
        column = gtk.TreeViewColumn(_('Value'), gtk.CellRendererText(),
                                     text=COLUMN_VALUE)
        self.treeview.append_column(column)
        
        # column for units
        column = gtk.TreeViewColumn(_('Unit'), gtk.CellRendererText(),
                                     text=COLUMN_UNIT)
        self.treeview.append_column(column)
        
        
    def _pid_active_toggled(self, cell, path, model):

        iter = model.get_iter((int(path),))
        active = model.get_value(iter, COLUMN_ACTIVE)
        model.set(iter, COLUMN_ACTIVE, not active)
        

        
    def start(self):
        if not self.status == STATUS_WORKING:
            self._timeout_id = self.garmon.connect('timeout', self._timeout_cb)
            self._update_status(STATUS_WORKING)
            
            
            
    def stop(self):
        if not self.status == STATUS_STOP:
            self._do_stop()
            self._update_status(STATUS_STOP)
        
        
        
    def _do_stop(self):
        if self._timeout_id:
            self.garmon.disconnect(self._timeout_id)
            self._timeout_id = None



    def _timeout_cb(self, garmon, data):
        self.treemodel.foreach(self._update_active_sensors)
        
        
        
    def _update_active_sensors(self, model, path, iter):
        active, pid, num = model.get(iter, COLUMN_ACTIVE, COLUMN_PID, COLUMN_NUM)
        if active:
            try:
                ret_pid, ret_num, metric, imperial = self.garmon.obd.get_sensor(pid, num)
            except (OBDPortError, OBDDataError):
                model.set(iter, COLUMN_VALUE, _('Error'))
                return
            if ret_pid != pid or ret_num != num:
                print 'Error in _update_active_sensors: ret_pid != pid'
                return
            
            if self.units == 'Imperial':
                model.set(iter, COLUMN_VALUE, imperial)
            else:
                model.set(iter, COLUMN_VALUE, metric)
                
        
    def unload(self):
        pass


    def _on_reset(self, garmon):
        if not self.status == STATUS_STOP:
            self.stop()
        self.treemodel.clear()
        if garmon.obd:
            self.pids = garmon.obd.supported_pids
            self._populate_treeview()
        

    def _populate_treeview(self):
        for pid in self.pids:
            num = obd_port.num_values(pid)
            for i in range(num):
                iter = self.treemodel.append(None)
                if self.units == 'Imperial':
                    units = Sensors[pid][i][IMPERIAL]
                else:
                    units = Sensors[pid][i][METRIC]
                self.treemodel.set(iter,
                                            COLUMN_ACTIVE, True,
                                            COLUMN_PID, pid,
                                            COLUMN_NUM, i,
                                            COLUMN_DESCRIPTION, Sensors[pid][i][NAME],
                                            COLUMN_VALUE, None,
                                            COLUMN_UNIT, units)      
                                        

    def _on_units_changed(self, garmon, units):
        self.units = units
        was_working = False
        
        if self.status == STATUS_WORKING:
            was_working = True
            self.stop()
                        
        self.treemodel.clear()
        self._populate_treeview()
        
        if was_working:
            self.start()
            
            
    def _on_page_changed(self, garmon, plugin):
        if plugin is self:
            if self.status == STATUS_PAUSE:
                self.start()
        else:
            if self.status == STATUS_WORKING:
                self._do_stop()
                self._update_status(STATUS_PAUSE)
            
            
                                   

