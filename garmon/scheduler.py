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

import garmon
from garmon.obd_device import OBDDevice
from garmon.property_object import PropertyObject, gproperty
from garmon.sensor import OBDData


class QueueItem(str):
    def __init__(self, command):
        str.__init__(self, command)
        
        self.list = []
        
        

class Scheduler (GObject, PropertyObject):
    """ This class receives OBDData objects, puts them in a queue
        and sends them to the OBDDevice
    """
    __gtype_name__ = "Scheduler"
    
    ################# Properties and signals ###############    
    gproperty('working', bool, False)
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
        
               
    def __init__(self, obd_device):
        """ @param obd_device: the OBDDevice to send commands
            @param timeout: the time between two commands
        """
        GObject.__init__(self)
        PropertyObject.__init__(self, obd_device=obd_device)
        self._queue = []
        self._os_queue = []
     
    def __post_init__(self):
        self.connect('notify::working', self._notify_working_cb)
        self.obd_device.connect('connected', self._obd_device_connected_cb)
    
    
    def _notify_working_cb(self, o, pspec):
        if self.working:
            self._execute_next_command()    
    
    
    def _command_success_cb(self, cmd, result, args):
        #we only care aboutthe first result
        result = result[0]
        for obd_data in cmd.list:
            obd_data.data = result
        if self.working:
            self._execute_next_command()
        
    def _command_error_cb(self, cmd, msg, args):
        debug('Scheduler._command_error_cb: command was: %s' % cmd)
        debug('Scheduler._command_error_cb: msg is %s' % msg)
        if self.working:
            self._execute_next_command()    
    
        
    def _execute_next_command(self):
        if len(self._os_queue):
            queue_item = self._os_queue.pop(0)
        elif len(self._queue):
            queue_item = self._queue.pop(0)
            self._queue.append(queue_item)
        else:
            #no commands anymore
            self.working = False
            return
            
        self.obd_device.read_obd_data(queue_item, 
                                          self._command_success_cb,
                                          self._command_error_cb)

    
    
    def _obd_device_connected_cb(self, obd_device, connected):
        if not connected:
            self.working = False
            
    ####################### Public Interface ###################
                           
    def add(self, obd_data, oneshot=False):
        """Add an item to the queue
           @param obd_data: the item to add to the queue
           @param oneshot: wether the command should only be 
                           executed once.
        """
        if not isinstance(obd_data, OBDData):
            raise ValueError, 'obd_data should be an instance of OBDData'
        if oneshot:
            queue = self._os_queue
        else:
            queue = self._queue
            
        if obd_data.pid in queue:
            queue_item = queue[queue.index(obd_data.pid)]
        else:
            queue_item = QueueItem(obd_data.pid)
            queue.append(queue_item)
        queue_item.list.append(obd_data)

           
    def remove(self, obd_data):
        """Remove an item from the queue
           @param obd_data: OBDData instance
        """
        if not isinstance(obd_data, OBDData):
            raise ValueError, 'obd_data should be an instance of OBDData'

        for queue in (self._queue, self._os_queue):
            for queue_item in queue:
                if queue_item == obd_data.pid:
                    if obd_data in queue_item.list:
                        queue_item.list.remove(obd_data)
                    if queue_item.list == []:
                        queue.remove(queue_item)
    
                  
