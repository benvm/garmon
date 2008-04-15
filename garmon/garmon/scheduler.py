#!/usr/bin/python
#
# scheduler.py
#
# Copyright (C) Ben Van Mechelen 2008 <me@benvm.be>
# 
# scheduler.py is free software; you can redistribute it and/or modify
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


import gobject
from gobject import GObject
import gtk

from obd_device import OBDDevice
from property_object import PropertyObject, gproperty
from sensor import OBDData


class Scheduler (GObject, PropertyObject):
    """ This class receives OBDData objects, puts them in a queue
        and sends them to the OBDDevice
    """
    __gtype_name__ = "Scheduler"
    
    ################# Properties and signals ###############    
    gproperty('working', bool, False)
    gproperty('timeout', int, 500)
    gproperty('obd-device', object)

    def prop_set_obd_device(self, device):
        if device and not isinstance(device, OBDDevice):
            raise TypeError, 'obd should be an instance of OBDDevice'
        return device
    
    def prop_set_working(self, working):
        if working:
            if self.obd_device and self.obd_device.connected:
                return working
            else:
                working = False
        return working
        
               
    def __init__(self, obd_device, timeout):
        """ @param obd_device: the OBDDevice to send commands
            @param timeout: the time between two commands
        """
        GObject.__init__(self)
        PropertyObject.__init__(self, obd_device=obd_device, timeout=timeout)
        self._queue = []
        self._timeout = None
     
    def __post_init__(self):
        self._timeout = gobject.timeout_add(self.timeout, self._timeout_cb)
        self.connect('notify::timeout', self._notify_timeout_cb)
        self.obd_device.connect('connected', self._obd_device_connected_cb)
        
            
    def _notify_timeout_cb(self, o, pspsec):
        gobject.source_remove(self._timeout)
        self._timeout = gobject.timeout_add(self.timeout, self._timeout_cb)
    
    def _timeout_cb(self):
        if self.obd_device:
            if self.working:
                self._execute_next_item()
        else:
            self.working = False
            print 'Scheduler Error: obd=None' 
        return True
        
    def _execute_next_item(self):
        if len(self._queue):
            queue_item = self._queue.pop(0)
            cmd, oneshot = queue_item
            if not oneshot:
                self._queue.append(queue_item)
            if isinstance(cmd, OBDData):
                cmd.data = self.obd_device.get_obd_data(cmd.pid)
    
    def _obd_device_connected_cb(self, obd_device, connected):
        if not connected:
            self.working = False
            
    ####################### Public Interface ###################
                           
    def add(self, item, oneshot=False):
        """Add an item to the queue
           @param item: the item to add to the queue
           @param oneshot: wether the command should only be 
                           executed once.
        """
        queue_item = (item, oneshot)
        self._queue.append(queue_item)
           
    def remove(self, obd_data):
        """Remove an item from the queue
           @param obd_data: OBDData instance
        """
        if not isinstance(obd_data, OBDData):
            raise ValueError, 'obd_data should be an instance of OBDData'
        for queue_item in self._queue:
            if queue_item[0] is obd_data:
                self._queue.remove(queue_item)
    
                  
