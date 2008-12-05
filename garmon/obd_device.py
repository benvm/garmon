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
from garmon.sensor import SENSORS, OBD_DESIGNATIONS, METRIC, IMPERIAL
from garmon.sensor import dtc_decode_num, dtc_decode_mil

from garmon import logger

import datetime

MAX_TIMEOUT = 3

class OBDError(Exception):
    """Base class for exceptions in this module"""

class OBDPortError(OBDError):
    """Exception to indicate that there was an error with the port"""

class OBDDataError(OBDError):
    """Exception to indicate a data error"""



class OBDDevice(GObject, PropertyObject):
    __gtype_name__ = "OBDDevice"
    
    _special_commands = {}
    _supported_pids = []
    _supported_freeze_frame_pids = None
    _connected = False 
    
    gsignal('connected', bool)
    
    gproperty('portname', str)
    #gproperty('initial-baudrate', int, 38400)
    gproperty('baudrate', int, 9600)
    gproperty('connected', bool, False, flags=gobject.PARAM_READABLE)
    gproperty('supported_pids', object, flags=gobject.PARAM_READABLE)
    gproperty('supported_freeze_frame_pids', object, flags=gobject.PARAM_READABLE)
    gproperty('special_commands', object, flags=gobject.PARAM_READABLE)
    gproperty('supported_commands', object, flags=gobject.PARAM_READABLE)
    

    def prop_get_connected(self):
        return self._connected

    def prop_get_supported_pids(self):
        return self._supported_pids

    def prop_get_supported_freeze_frame_pids(self):
        if self._supported_freeze_frame_pids == None:
            self.read_supported_freeze_frame_pids()
            return None
        else:
            return self._supported_freeze_frame_pids
        
    def prop_get_special_commands(self):
        return self._special_commands
        
    def prop_get_supported_commands(self):
        commands = self._special_commands.keys()
        for pid in self.supported_pids:
            commands.append(pid)
        return commands
        
    def prop_set_baudrate(self, baudrate):
        if hasattr(self, '_port') and self._port:
            self._port.baudrate = baudrate
        return baudrate 
        

    def __init__(self):
        GObject.__init__(self)
        PropertyObject.__init__(self)

    ####################### Public Interface ###################
    
    def open(self, portname):
        raise NotImplementedError
    def close(self):
        raise NotImplementedError
    def read_obd_data(self, command, ret_cb, err_cb, *args):
        raise NotImplementedError
    def read_dtc(self, ret_cb, err_cb, *args):
        raise NotImplementedError
    def clear_dtc(self, ret_cb, err_cb, *args):
        raise NotImplementedError
    def get_dtc_num(self, ret_cb, err_cb, *args):
        raise NotImplementedError
    def get_mil(self, ret_cb, err_cb, *args): 
        raise NotImplementedError
    def read_device_data(self, command, ret_cb, err_cb, *args):
        raise NotImplementedError
    def read_command(self, ret_cb, err_cb, *args):
        raise NotImplementedError
    def read_supported_freeze_frame_pids(self):
        raise NotImplementedError

class ELMDevice(OBDDevice, PropertyObject):
    """ This class talks to an ELM device. It sends commands and receives
        data from it.
    """
    __gtype_name__ = "ELMDevice"
    
    _special_commands = {
                        'voltage'   : ('atrv', 'V'),
                        'protocol'  : ('atdp', ''),
                        }
     
    
    def __init__(self):
        OBDDevice.__init__(self)
        PropertyObject.__init__(self)

        # TODO: ignore for the moment (see request_baudrate)
        # self._current_baudrate = self.initial_baudrate
        # self._requested_baudrate = None

        self._connected = False
        self._port = None
        self._watch_id = None
        
        self._supported_pids = []
        
        self._sent_command = None
        self._cleanup_command = True
        self._ret_cb = None
        self._err_cb = None
        self._cb_args = None
    
    
    def __post_init__(self):
        self.connect('notify::portname', self._notify_portname_cb)
            
        
    def _notify_portname_cb(self, o, pspec):
        if self._port and self._port.isOpen():
            self.close()
            self.open()


    def _send_command(self, command, ret, err, cleanup=True, *args):
        print 'in _send_command; command is %s' % command
        if not self._port.isOpen():
            raise OBDPortError('PortNotOpen', _('The port is not open'))

        self._cleanup_command = cleanup
        self._sent_command = command
        self._ret_cb = ret
        self._err_cb = err
        self._cb_args = args
        try:
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
        try:
            buf = ''
            while timeout_count <= MAX_TIMEOUT:
                ch = self._port.read(1)
                if ch == '':
                    timeout_count += 1
                if ch == '>': 
                    break
                else:
                    buf = buf + ch
            if buf == '':
                raise OBDPortError('PortIOFailed', 
                                   _('Read timeout from ') + self.portname)
            buf = buf.replace('\r\r', '')
            return buf
            
        except serial.SerialException:
            raise OBDPortError('PortIOFailed', 
                               _('Unable to read from ') + self.portname)
                                          
                
        return None
         
      
    def _parse_result(self, data):
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
                
            elif data[0] == '?':
                print 'command sent, received ?'
                error = True
                msg = '?'
                
            elif 'SEARCHING' in data:
                print 'received SEARCHING: resending command'
                self._send_command(cmd, ret_cb, err_cb, args)
                
            elif 'UNABLE TO CONNECT' in data:
                print 'received UNABLE TO CONNECT'
                error = True
                msg = 'UNABLE TO CONNECT'

            elif 'NO DATA' in data:
                print 'received NO DATA'
                error = True
                msg = 'NO DATA'
                
            else:
                res = data
                success = True
                
            if self._cleanup_command:
                self._err_cb = None
                self._ret_cb = None
                self._sent_command = None
                self._cb_args = None
                
            if error:
                err_cb(cmd, msg, args)
                
            if success:
                ret_cb(cmd, data, args)
                
        else:
            # no command sent
            # are we interested anyway?
            if '>' in data:
                print 'received >'
            else:
                print 'no command sent, received %s' % data
                

    def _port_io_watch_cb(self, fd, condition, data=None):
        print 'in _port_io_watch_cb'
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
        elif condition & gobject.IO_IN:
            try:
                result = self._read_result()
                self._parse_result(result)
            except OBDPortError, e:
                debug('CONDITION = IO_IN but reading times out. Error: %s' % e[0])
            finally:
                return True
        else:
            debug('received an unknown io signal')
            return False

  
    
    def _read_supported_pids(self, freeze_frame=False):
        #FIXME: merge these 3 in a single function
        def zero_success_cb(cmd, data, args):
            self._supported_pids += decode_pids_from_bitstring(data)
            if '0120' in self._supported_pids:
                self._send_command('0120', twenty_success_cb, error_cb)
            else:
                self._connected = True
                print 'supported pids: %s' % self._supported_pids
                self.emit('connected', True)

        def twenty_success_cb(cmd, data, args):
            self._supported_pids += decode_pids_from_bitstring(data, 32)
            if '0140' in self._supported_pids:
                self._send_command('0140', forty_success_cb, error_cb)
            else:
                self._connected = True
                print 'supported pids: %s' % self._supported_pids
                self.emit('connected', True)
                
        def forty_success_cb(cmd, data, args):
            self._supported_pids += decode_pids_from_bitstring(data, 64)
            self._connected = True
            print 'supported pids: %s' % self._supported_pids
            self.emit('connected', True)
                                
        def ff_success_cb(cmd, data, args):
            self._supported_freeze_frame_pids = []
            data = decode_result(data)
            for item in data:
                bitstr = sensor.hex_to_bitstr(item)
                for i, bit in enumerate(bitstr):
                    if bit == "1":
                        pid = i + 1
                        if pid < 16: 
                            pid_str = '020' + hex(pid)[2:]                    
                        else:
                            pid_str = '02' + hex(pid)[2:]
                        self._supported_freeze_frame_pids.append(pid_str.upper())  
                        
            print 'supported freeze frame pids: %s' % self._supported_freeze_frame_pids

        def error_cb(cmd, msg, args):
            debug('error reading supported pids, msg is: %s' % msg)
            raise OBDPortError('OpenPortFailed', 
                               _('could not read supported pids\n\n' + msg))        
        
        if freeze_frame:
            if self._connected:
                self._send_command('0200', ff_success_cb, error_cb)        
        else:
            self._supported_pids = []
            self._send_command('0100', zero_success_cb, error_cb)
        
      
        
    def _initialize_device(self):
        def atz_success_cb(cmd, res, args):
            print 'in atz_success_cb'
            if not 'ELM327' in res:
                print 'invalid response'
                atz_error_cb(cmd, res, None)
            else:
                print 'received answer valid'
                self._send_command('ate0', ate_success_cb, ate_error_cb) 
            
        def atz_error_cb(cmd, msg, args):
            print 'in atz_error_cb'
            raise OBDPortError('OpenPortFailed', 
                               _('atz command failed'))
            
        def ate_success_cb(cmd, res, args):
            print 'in ate_success_cb'
            if not 'OK' in res:
                print 'invalid response'
                ate_error_cb(cmd, res, args)
            else:
                self._read_supported_pids()
            
        def ate_error_cb(cmd, msg, args):
            print 'in atz_error_cb'
            raise OBDPortError('OpenPortFailed', 
                               _('ate0 command failed'))
           
        self._send_command('atz', atz_success_cb, atz_error_cb)                        
    
                               
                               
                                       
    ####################### Public Interface ###################
                
    def open(self, portname=None):
        self._supported_pids = []
        self._supported_freeze_frame_pids = None
        if portname:
            self.portname = portname
        if not self.portname:
            raise OBDPortError('OpenPortFailed', 
                                _('No portname has been set.'))
            
        try:
            self._port = serial.Serial(self.portname, self.baudrate, 
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
        self._supported_freeze_frame_pids = None
        if self._port:
            gobject.source_remove(self._watch_id)
            self._port.close()
        self._connected = False
        self.emit('connected', False)
        
                    
    def request_baudrate(self, baudrate=None):
        """FIXME: Ignore this for the moment.
           Setting the baudrate with AT BRD xx needs more investigation"""
        raise NotImplementedError
        if not baudrate:
            #FIXME: implement this
            #self._request_highest_baudrate()
            pass
        else:
        
            divisor = hex(int(round(4000000.0 / baudrate)))
            command = 'at brd ' + str(divisor)[2:]
        
            def cr_return_cb(cmd, res, args):
                print 'cr_return_cb'
                if 'OK' in res:
                    self._current_baudrate = baudrate
                
            def brd_support_success_cb(cmd, res, args):
                if 'OK' in res:
                    print 'res = OK'
                    self._port.baudrate = baudrate
                    print self._stop - self._start
                elif 'ELM327' in res:
                    print 'res = ELM327'
                    self._send_command('\r', cr_success_cb, error_cb)    
                
                
            def error_cb(cmd, msg, args):
                if msg == '?':
                    #FIXME
                    print 'BRD command not supported'
                else:
                    print 'error in request_baudrate %s' % msg
                    self._port.baudrate = self.initial_baudrate
                    self._current_baudrate = self.initial_baudrate
                
            self._send_command(command, brd_support_success_cb, error_cb)
            
    
    
    def read_pid_data(self, pid, ret_cb, err_cb, *args):
        if not pid in self._supported_pids and \
           not pid in self._supported_freeze_frame_pids:
            raise ValueError, 'pid %s is not supported' % pid
        
        def success_cb(cmd, res, args):
            res = decode_result(res)
            ret_cb(cmd, res, args)

        if self._port and self._port.isOpen():
            self._send_command(pid, success_cb, err_cb, args)
        else:
            raise OBDPortError('PortNotOpen', _('The port is not open'))        
    
    
    def read_device_data(self, command, ret_cb, err_cb, *args):
        if not command in self._special_commands.keys():
            raise ValueError, 'command %s is not supported' % command
            
        def success_cb(cmd, res, args):
            ret = []
            ret.append(res)
            ret_cb(command, ret, args)
            
        def error_cb(cmd, res, args):
            err_cb(command, res, args)

        if self._port and self._port.isOpen():
            cmd = self._special_commands[command][0]
            self._send_command(cmd, success_cb, error_cb, args)
        else:
            raise OBDPortError('PortNotOpen', _('The port is not open'))              
       

    def read_command(self, command, ret_cb, err_cb, *args):
          
        if command in self._special_commands.keys():
            self.read_device_data(command, ret_cb, err_cb, args)
        elif command[:2] == '01' and command in self._supported_pids:
            self.read_pid_data(command, ret_cb, err_cb, args)
        elif command[:2] == '02' and command in self._supported_freeze_frame_pids:
            self.read_pid_data(command, ret_cb, err_cb, args)
        else:
            raise NotImplementedError, 'This command is currently not supported'
    
    
    def get_dtc_num(self, ret_cb, err_cb, *args):

        def success_cb(cmd, result, args):
            result = dtc_decode_num(result)[0]
            ret_cb(cmd, result, args)
           
        self._read_obd_data('0101', success_cb, err_cb, args)
        
        
    def get_mil(self, ret_cb, err_cb, *args):
        
        def success_cb(cmd, result, args):
            result = dtc_decode_mil(result)[0]
            ret_cb(cmd, result, args)
           
        self._read_obd_data('0101', success_cb, err_cb, args)

        
    def read_dtc(self, ret_cb, err_cb, *args):

        def success_cb(cmd, result, args):
            try:
                dtc = decode_dtc_result(result)
            except OBDError, (err, msg):
                err_cb(cmd, err, args)
            ret_cb(cmd, dtc, args)
        
        if self._port and self._port.isOpen():
            self._send_command('03', success_cb, err_cb, args)
        else:
            raise OBDPortError('PortNotOpen', _('The port is not open'))


    def clear_dtc(self, ret_cb, err_cb, *args):
    
        def success_cb(cmd, result, args):
            if result:
                result = string.split(result, "\r")
                result = result[0]

                result = string.split(result)
                result = string.join(result, "")
                result = result[:2]
                
                if result == '44':
                    ret_cb(cmd, result, args)
                else:
                    err_cb(cmd, OBDDataError, args)
            else:
                err_cb(cmd, OBDDataError, args)

        if self._port and self._port.isOpen():
            self._send_command('04', success_cb, err_cb, args)
        else:
            raise OBDPortError('PortNotOpen', _('The port is not open'))                
                
                
                
    def read_supported_freeze_frame_pids(self):
        self._read_supported_pids(True)       



def decode_dtc_result(result):
    if not result:
        raise OBDDataError('DataReadError',
                           _('No data was received from the device'))
    dtc = []

    result = string.split(result, "\r")
    for data in result:
    
        if data:
            if not data[:2] == '43':
                raise OBDDataError('Data Read Error',
                             _('Did not get a mode 03 result from the device'))
            data = data[2:]
            data = string.split(data)
            data = string.join(data, '')
            if not len(data) == 12:
                raise OBDDataError('Data Read Error',
                                     _('Did not get a valid length of data'))
            for i in xrange(3):
                if not data[:4] == '0000':
                    dtc.append(data[:4])
                data = data[4:]
    return dtc

                           
                           
def decode_result(result):
    print 'entering decode_result'
    if not result:
        raise OBDDataError('Data Read Error',
                           _('No data was received from the device'))
    ret = []
    
    result = string.split(result, "\r")

    for data in result:
        if data:
            data = string.split(data)
            data = string.join(data, '')
            
            if data[:2] == '7F':
                print 'we got back 7F which is an error'
            else:
                ret.append(data[4:])
        
    return ret
    
    
def decode_pids_from_bitstring(data, offset=0):
    pids = []
    data = decode_result(data)
    for item in data:
        bitstr = sensor.hex_to_bitstr(item)
        for i, bit in enumerate(bitstr):
            if bit == "1":
                pid = i + 1 + offset
                if pid < 16: 
                    pid_str = '010' + hex(pid)[2:]                    
                else:
                    pid_str = '01' + hex(pid)[2:]
                pids.append(pid_str.upper())
    return pids
