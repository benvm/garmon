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
from garmon.sensor import OBDData, SENSORS, OBD_DESIGNATIONS, METRIC, IMPERIAL
from garmon.sensor import dtc_decode_num, dtc_decode_mil

from garmon import debug

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
        self._watch_id = None
        
        self._supported_pids = []
        
        self._sent_command = None
        self._ret_cb = None
        self._err_cb = None
    
    
    def __post_init__(self):
        self.connect('notify::portname', self._notify_portname_cb)
            
        
    def _notify_portname_cb(self, o, pspec):
        if self._port and self._port.isOpen():
            self.close()
            self.open()

       
    def _read_pid(self, pid):
        print 'entering OBDDevice._read_pid'
        
        self._send_obd_command(pid)
        result = self._read_result()
        print 'result from _read_result is: %s' % result

            
        if result:
            result = string.split(result, "\r")
            result = result[0]

            result = string.split(result)
            result = string.join(result, "")
            print 'result is %s' % result

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
                                            


    def _send_command(self, command, ret, err, *args):
        print 'in _send_command; command is %s' % command
        if not self._port.isOpen():
            raise OBDPortError, 'PortNotOpen'
        #FIXME: should we check if the current character is ">"
        try:
            self._sent_command = command
            self._ret_cb = ret
            self._err_cb = err
            self._cb_args = args
            self._port.flushOutput()
            self._port.flushInput()
            self._port.write(command)
            self._port.write("\r")
        except serial.SerialException:
            self._sent_command = None
            self._ret_cb = None
            self._err_cb = None
            self._cb_args = None
            self.close()           
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
                    if ch == '>' and len(buf) > 1 and buf[-1] == '\r' and buf[-2] == '\r':
                        break
                    else:
                        buf = buf + ch
                if buf == '':
                    raise OBDPortError('PortIOFailed', 
                                       _('Read timeout from ') + self.portname)
                return buf
                
            except serial.SerialException:
                raise OBDPortError('PortIOFailed', 
                                   _('Unable to read from ') + self.portname)
                                              
                
        return None
        
      
    def _decode_result(self, result):
        print 'entering OBDDevice._decode_result'
            
        if result:
            result = string.split(result, "\r")
            result = result[0]

            result = string.split(result)
            result = string.join(result, "")
            print 'result is %s' % result
            
            result = result[4:]
            
            return result

        else: 
            raise OBDDataError('Data Read Error',
                               _('No data was received from the device'))

      
      
    def _parse_result(self, data):
        print 'entering _parse_result'
        error = False
        success = False
        res = None
        msg = None
        
        cmd = self._sent_command
        err_cb = self._err_cb
        ret_cb = self._ret_cb
        args = self._cb_args
        
        if self._sent_command:
            if data[0] == '>':
                print 'command sent, received >'
                error = True

            elif data[:2] == 'OK' or data[:4] == 'ate0':
                if self._sent_command == 'ate0':
                    print 'command sent, received OK'
                    res = 'OK'
                    success = True
                    
            elif 'ELM327' in data or data[:3] == 'atz':
                if self._sent_command == 'atz':
                    print 'command sent, received ELM327'
                    res = data
                    success = True

            elif 'SEARCHING' in data:
                print 'received SEARCHING'
                self._send_command(cmd, ret_cb, err_cb, args)
                
            elif 'UNABLE TO CONNECT' in data:
                print 'received UNABLE TO CONNECT'
                error = True
                msg = 'UNABLE TO CONNECT'

            elif 'NO DATA' in data:
                print 'received NO DATA'
                error = True
                msg = 'NO DATA'
                                
            elif data[:2] == '7F':
                print 'received 7F: error'
                error = True
                
            elif data[0] == '4':
                res = self._decode_result(data)
                success = True
                
            if error:
                self._err_cb = None
                self._ret_cb = None
                self._sent_command = None
                self._cb_args = None
                err_cb(cmd, msg, args)
                
            if success:
                self._err_cb = None
                self._ret_cb = None
                self._sent_command = None
                self._cb_args = None
                ret_cb(cmd, res, args)
                
        else:
            # no command sent
            # are we interested anyway?
            if '>' in data:
                print 'received >'
            else:
                print 'no command sent, received %s' % data
                

    def _port_io_watch_cb(self, fd, condition, data=None):
        print 'in _on_io_activity'
        if condition & gobject.IO_HUP:
            debug('received HUP signal')
            self._sent_command = None
            self._ret_cb = None
            self._err_cb = None
            self._cb_args = None
            self.close()    
            return False
        elif condition & gobject.IO_ERR:
            debug('received ERR signal')
            self._sent_command = None
            self._ret_cb = None
            self._err_cb = None
            self._cb_args = None
            self.close()    
            return False
        elif condition & gobject.IO_IN or condition & gobject.IO_PRI:
            try:
                result = self._read_result()
                self._parse_result(result)
            except OBDPortError:
                debug('CONDITION = IO_IN but reading times out')
            finally:
                return True
        else:
            debug('received an unknown io signal')
            return False
    
    
    def _read_supported_pids(self):
    
        def success_cb(cmd, data, args):
            self._supported_pids = []

            bitstr = sensor.hex_to_bitstr(data)
        
            for i in range(0, len(bitstr)):
                if bitstr[i] == "1":
                    pid = i + 1
                    if pid < 16: 
                        pid_str = '010' + hex(pid)[2:]                    
                    else:
                        pid_str = '01' + hex(pid)[2:]
                    self._supported_pids.append(pid_str.upper())      
                          
            self._connected = True
            self.emit('connected', True)
        
        def error_cb(cmd, msg, args):
            debug('error reading supported pids, msg is: %s' % msg)
            raise OBDPortError('OpenPortFailed', 
                               _('could not read supported pids\n\n' + msg))        
        
        self._send_command('0100', success_cb, error_cb)
                
        
        
    def _initialize_device(self):
        def atz_success_cb(cmd, res, args):
            print 'in atz_success_cb'
            self._send_command('ate0', ate_success_cb, ate_error_cb) 
            
        def atz_error_cb(cmd, msg, args):
            print 'in atz_error_cb'
            raise OBDPortError('OpenPortFailed', 
                               _('atz command failed'))
            
        def ate_success_cb(cmd, res, args):
            print 'in ate_success_cb'
            self._read_supported_pids()
            
        def ate_error_cb(cmd, msg, args):
            print 'in atz_error_cb'
            raise OBDPortError('OpenPortFailed', 
                               _('ate0 command failed'))
           
        self._send_command('atz', atz_success_cb, atz_error_cb)                        
    
                               
                               
                                       
    ####################### Public Interface ###################
                
    def open(self, portname=None):
        self._supported_pids = []
        if portname:
            self.portname = portname
        if not self.portname:
            raise OBDPortError('OpenPortFailed', 
                                _('No portname has been set.'))
            
        try:
            self._port = serial.Serial(self.portname, 9600, 
                                  serial.EIGHTBITS,
                                  serial.PARITY_NONE,
                                  serial.STOPBITS_ONE,
                                  timeout = 1)
        except serial.SerialException:
            raise OBDPortError('OpenPortFailed', 
                               _('Unable to open %s') % self.portname)
        self._watch_id = gobject.io_add_watch(self._port, 
              gobject.IO_IN | gobject.IO_PRI | gobject.IO_ERR | gobject.IO_HUP,
              self._port_io_watch_cb)                                  
        
        self._initialize_device()

        
    def close(self):
        """Resets the elm chip and closes the open serial port""" 
        self._supported_pids = []
        if self._port:
            self._port.close()
            gobject.source_remove(self._watch_id)
            if self._connected:
                self._connected = False
                self.emit('connected', False)
        
                    
    def read_obd_data(self, command, ret, err, *args):
        if not command in self._supported_pids and \
           not command in self._special_commands:
           raise ValueError, 'command %s is not supported' % command
           
        self._send_command(command, ret, err, args)
          
          
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
                    if not len(result) == 12:
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
                               
                               
                               
