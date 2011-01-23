#!/usr/bin/python
#
# scheduler.py
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
from gettext import gettext as _
import datetime

import inspect

import garmon
from garmon.obd_device import OBDDevice
from garmon.property_object import PropertyObject, gproperty, gsignal
from garmon.sensor import Command
from garmon import logger


class QueueItem(str):
    def __init__(self, command):
        str.__init__(self)
        self.oneshot = False
        self.list = []

        

class Scheduler (GObject, PropertyObject):
    """ This class receives OBDData objects, puts them in a queue
        and sends them to the OBDDevice
    """
    __gtype_name__ = "Scheduler"
    
    ################# Properties and signals ###############    
    gsignal('command-executed')
    gsignal('state-changed', bool)
    
    gproperty('obd-device', object)
    gproperty('working', bool, False)

    def prop_set_obd_device(self, device):
        if device and not isinstance(device, OBDDevice):
            raise TypeError, 'obd should be an instance of OBDDevice'
        return device
    
    def prop_get_working(self):
        return self._working
        
               
    def __init__(self, obd_device):
        """ @param obd_device: the OBDDevice to send commands
            @param timeout: the time between two commands
        """
        GObject.__init__(self)
        PropertyObject.__init__(self, obd_device=obd_device)
        self._queue = []

        self._working = False
     
    def __post_init__(self):
        self.obd_device.connect('connected', self._obd_device_connected_cb)
    
    def start(self):
        logger.debug('Scheduler.start')
        if not self._working:
            self._working = True
            self.emit('state-changed', self._working)
        self._execute_next_command()

    def stop(self):
        logger.debug('Scheduler.stop')
        if self._working:
            self._working = False
            self.emit('state-changed', self._working)
        self._working = False

        
    def _notify_working_cb(self, o, pspec):
        if self._working:
            self._execute_next_command()
    
    
    def _command_success_cb(self, cmd, result, args):
        logger.debug('entering Scheduler._command_success_cb: %s' % cmd)
        # We only care about the first result
        result = result[0]
        for item in cmd.list:
            item.data = result
        self._execute_next_command()
            
    def _command_error_cb(self, cmd, msg, args):
        logger.debug('Scheduler._command_error_cb: command was: %s' % cmd)
        logger.debug('Scheduler._command_error_cb: msg is %s' % msg)
        if self._working:
            self._execute_next_command()
    
    
    def _execute_next_command(self):
        logger.debug('entering Scheduler._execute_next_command')
        if self._working:
            if len(self._queue):
                queue_item = self._queue.pop(0)
                if not queue_item.oneshot:
                    self._queue.append(queue_item)
            else:
                logger.debug('Scheduler: nothing in queue')
                self.stop()
                return
        
            logger.debug('Scheduler: executing next command: %s' % queue_item  ) 
            self.obd_device.read_command(queue_item, 
                                              self._command_success_cb,
                                              self._command_error_cb)

    
    
    def _obd_device_connected_cb(self, obd_device, connected):
        if not connected:
            self.stop()
            
    ####################### Public Interface ###################
                           
    def add(self, cmd, oneshot=False):
        """Add an item to the queue
           @param cmd: the item to add to the queue
           @param oneshot: wether the command should only be 
                           executed once.
        """
        if not isinstance(cmd, Command):
            raise ValueError, 'command should be an instance of Command'
            
        if cmd.command in self._queue:
            queue_item = self._queue[self._queue.index(cmd.command)]
        else:
            queue_item = QueueItem(cmd.command)
            queue_item.oneshot = oneshot
            self._queue.append(queue_item)
        queue_item.list.append(cmd)

           
    def remove(self, cmd):
        """Remove an item from the queue
           @param cmd: Command instance
        """
        if not isinstance(cmd, Command):
            raise ValueError, 'cmd should be an instance of Command'

        for queue_item in self._queue:
            if queue_item == cmd.command:
                if cmd in queue_item.list:
                    queue_item.list.remove(cmd)
                if queue_item.list == []:
                    self._queue.remove(queue_item)
    
    
class SchedulerTimer(gtk.Label, PropertyObject):
    
    gproperty('active', bool, False)

    def __init__(self, scheduler):
        GObject.__init__(self)
        PropertyObject.__init__(self)
        
        self._rate = 0
        self._samples = []
        self.set_text(_('refresh rate: N/A'))
        
        scheduler.connect('command_executed', self._scheduler_command_executed_cb)
        scheduler.connect('notify::working', self._scheduler_notify_working_cb)
                    
    def _scheduler_notify_working_cb(self, scheduler, working):
        if not working:
            self.set_text(_('refresh rate: N/A'))
    
    def _scheduler_command_executed_cb(self, scheduler):
        now = datetime.datetime.now()
        if len(self._samples) == 0:
            self._samples.append((now, datetime.timedelta(0,0,0)))
        else:
            if len(self._samples) > 20:
                self._samples.pop(0)
            previous = self._samples[len(self._samples) - 1]
            delta = now - previous[0]
            self._samples.append((now, delta))
            
            total = 0.0
            count = 0
            for item in self._samples:
                count += 1
                u_seconds = item[1].seconds + item[1].microseconds / 1000000.0
                total += u_seconds
                
            rate = round(count / total, 1)
            
            self.set_text(_('refresh rate: %s Hz') % rate)
        
        
        
        
