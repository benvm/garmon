#!/usr/bin/python
# -*- coding: iso-8859-15 -*-
#
# obd_device.py
#
# Copyright (C) Ben Van Mechelen 2007-2008 <me@benvm.be>
# 
# obd_device.py is free software; you can redistribute it and/or modify
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

import serial
import string
import math

import gobject
from gobject import GObject
from property_object import PropertyObject, gproperty, gsignal

import garmon
import garmon.sensor as sensor
from garmon.sensor import OBDSensor, SENSORS, OBD_DESIGNATIONS, METRIC, IMPERIAL
from garmon.sensor import dtc_decode_num, dtc_decode_mil
 

MAX_TIMEOUT = 3

class OBDError(Exception):
    """Base class for exceptions in this module"""     

class OBDPortError(OBDError):
    """Exception to indicate that there was an error with the port"""

class OBDDataError(OBDError):
    """Exception to indicate a data error"""


    
class OBDDevice(GObject, PropertyObject):
    """ This class talks to the ELM device. It sends commands and receives
        data from it.
    """
    #__gtype_name__ = "OBDDevice"
    
    _special_commands = {
                        'Voltage'     : 'RV'
                        }

    _special_command_functions = {}
    
    ################# Properties and signals ###############        
    
    gsignal('connected', bool)
    
    gproperty('portname', str)
    gproperty('connected', bool, False, flags=gobject.PARAM_READABLE)
    gproperty('supported_pids', object, flags=gobject.PARAM_READABLE)
    gproperty('special_commands', object, flags=gobject.PARAM_READABLE)
    

    def prop_get_connected(self):
        return self._connected

    def prop_get_supported_pids(self):
        return self._supported_pids
        
    def prop_get_special_commands(self):
        return self._special_commands
    
    
    def __init__(self, portname=None):
        """ @param portname: The port to connect to e.g. /dev/ttyUSB0
        """
        GObject.__init__(self)
        PropertyObject.__init__(self, portname=portname)

        self._connected = False
        self._port = None
        self._supported_pids = []
    
    
    def __post_init__(self):
        self.connect('notify::portname', self._notify_portname_cb)
            
        
    def _notify_portname_cb(self, o, pspec):
        if self._port and self._port.isOpen():
            self.close()
            self.open()

       
    def _read_pid(self, pid):
        
        self._send_obd_command(pid)
        result = self._read_result()

            
        if result:
            result = string.split(result, "\r")
            result = result[0]

            result = string.split(result)
            result = string.join(result, "")

            if result[:6] == 'NODATA':
                raise OBDDataError('PID Data Error',
                                   _('No data available for this pid'))
            
            result = result[4:]
            
            return result

        else: 
            raise OBDDataError('Data Read Error',
                               _('No data was received from the device'))

    
    def _read_special_command(self, command):
        self._send_obd_command(pid)
        result = self._read_result()
        
        if result:
            if pid in self._special_command_functions:
                return self._special_command_functions[pid](result)
            else:
                return result           
        else: 
            raise OBDDataError('Data Read Error',
                               _('No data was received from the device'))
                                            


    def _send_obd_command(self, command):
        if self._port.isOpen():
            try:
                self._port.flushOutput()
                self._port.flushInput()
                self._port.write(command)
                self._port.write("\r")
            except serial.SerialException:
                self._connected = False
                self.close()
                self.emit('connected', False)                            
                raise OBDPortError('PortIOFailed', 
                                   _('Unable to write to ') + self._portname)              
            
        
        
    def _read_result(self):
        timeout_count = 0
        if self._port.isOpen:
            try:
                buf = ''
                while timeout_count <= MAX_TIMEOUT:
                    ch = self._port.read(1)
                    if ch == '':
                        timeout_count += 1
                    if ch == '\r' and len(buf) > 0 and buf[-1] == '\r':
                        break
                    else:
                        buf = buf + ch
                if buf == '':
                    self._connected = False
                    self.close()
                    self.emit('connected', False)
                    raise OBDPortError('PortIOFailed', 
                                       _('Read timeout from ') + self.portname)
                return buf
                
            except serial.SerialException:
                self._connected = False
                self.close()
                self.emit('connected', False)
                raise OBDPortError('PortIOFailed', 
                                   _('Unable to read from ') + self.portname)
                                              
                
        return None
        
    def _get_supported_pids(self):
        self._supported_pids = []
        
        for r in ("00", "20"): # "40"
        
            self._send_obd_command("01"+r)
            res = self._read_result()[-9:-1]
            str = sensor.hex_to_bitstr(res)
        
            for i in range(0, len(str)):
                if str[i] == "1":
                    pid = eval("0x%s" % r) + i + 1
                    if pid < 16: 
                        pid_str = '010' + hex(pid)[2:]                    
                    else:
                        pid_str = '01' + hex(pid)[2:]
                    self._supported_pids.append(pid_str.upper())
            
            # Don't query 0120 or 0140 if they are not supported
            if not '0120' in self._supported_pids:
                break
                  
                                        
    ####################### Public Interface ###################
                
    def open(self, portname=None):
        self._supported_pids = []
        if not portname is None:
            self.portname = portname
            
        try:
            self._port = serial.Serial(self.portname, 19200, 
                                  serial.EIGHTBITS,
                                  serial.PARITY_NONE,
                                  serial.STOPBITS_ONE,
                                  timeout = 1)
        except serial.SerialException:
            raise OBDPortError('OpenPortFailed', 
                               _('Unable to open %s') % self.portname)
                                          
        
        self._send_obd_command("atz")    #Initialize the device
        self._send_obd_command("ate0")   #Make sure echo is off

        #Send a command to see if we are connected
        self._send_obd_command('0100')
        if self._read_result():
            self._connected = True
            self.emit('connected', True)
            self._get_supported_pids()
            

        
    def close(self):
        """Resets the elm chip and closes the open serial port""" 
        self._supported_pids = []
        if self._port and self._port.isOpen():
            self._send_obd_command("atz")
            self._port.close()
            if self._connected:
                self._connected = False
                self.emit('connected', False)
        

            
                                            
                                                
    def update_obd_data(self, obd_data):
        if not isinstance(obd_data, OBDData):
            raise TypeError, "object is not of type %s" % OBDData
        obd_data.data = self.get_obd_data(obd_data.pid)
          
                    
    def get_obd_data(self, pid):
        if pid in self._supported_pids:
            return self._read_pid(pid)
        elif pid in self._special_commands:
            return self._read_special_command(pid)
        else:
            debug('pid %s is not supported' % pid)
          
          
    def get_obd_designation(self):
        if '011C' in self.supported_pids:
            value = self._read_pid('011C')
            string = OBD_DESIGNATIONS[value[:2]]
        else:
            string = _('No designation reported')
            
        return string


    def get_voltage(self):
        if self._port and self._port.isOpen():
            self._send_obd_command('RV')
            result = self._read_result()
            result = result[:-2]
            return result
        return None


    def get_dtc_num(self):
        res = self._read_pid('0101')
        return dtc_decode_num(res)[0]
        
        
    def get_mil(self):
        res = self._read_pid('0101')
        return dtc_decode_mil(res)[0]
        
        
    def get_dtc(self):
        dtc = []
        if self._port and self._port.isOpen():
            try:
                num = self.get_dtc_num()
                self._send_obd_command('03')
                for i in range (int(math.ceil(num/3.0))):
                    result = self._read_result()
                    if not result[:2] == '43':
                        raise OBDDataError, _('Did not get a mode 03 result from the device')
                    result = result[2:]
                    result = string.split(result)
                    result = string.join(result, '')
                    if not result.__len__() == 12:
                        raise (OBDDataError, _('Did not get a valid length of data'))
                    for i in range(3):
                        if not result[:4] == '0000':
                            dtc.append(result[:4])
                        result = result[4:]
            except (OBDPortError, OBDDataError):
                raise#TODO: Finish
        
        return dtc 
            

    def clear_dtc(self):
        try:
            self._send_obd_command('04')
            result = self._read_result()
            
            if result:
                result = string.split(result, "\r")
                result = result[0]

                result = string.split(result)
                result = string.join(result, "")
                result = result[:2]
                
                return eval("0x%s" % result) & 0x40
            else:
                raise OBDDataError 
        except OBDPortError:
            raise
                
        
    def is_connected(self):
        return self._connected


def get_sensor_units(pid, index=0):
    if index <= len(SENSORS[pid]):
        metric = SENSORS[pid][index][METRIC]
        imperial = SENSORS[pid][index][IMPERIAL]
        return (metric, imperial)
    else:
        raise OBDError('PID Index Error',
                       _('Invalid index for that pid'))
                               
                               
                               
