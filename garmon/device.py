#!/usr/bin/python
# -*- coding: iso-8859-15 -*-
#
# device.py
#
# Copyright (C) Ben Van Mechelen 2007-2011 <me@benvm.be>
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

from gettext import gettext as _

import serial
import string
import math
import os

import gtk
import gobject
from gobject import GObject
from property_object import PropertyObject, gproperty, gsignal

import garmon
import garmon.sensor as sensor
from garmon.sensor import SENSORS, OBD_DESIGNATIONS, METRIC, IMPERIAL
from garmon.sensor import dtc_decode_num, dtc_decode_mil
from garmon.prefs import PreferenceManager

from garmon import logger, UI_DIR

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
    _connected = False 
    
    gsignal('connected', bool)
    gsignal('supported-pids-changed')
    
    gproperty('port', str, flags=gobject.PARAM_READABLE)
    #gproperty('initial-baudrate', int, 38400, flags=gobject.PARAM_READABLE)
    gproperty('baudrate', int, 9600, flags=gobject.PARAM_READABLE)
    gproperty('connected', bool, False, flags=gobject.PARAM_READABLE)
    gproperty('supported_pids', object, flags=gobject.PARAM_READABLE)
    gproperty('special_commands', object, flags=gobject.PARAM_READABLE)
    gproperty('supported_commands', object, flags=gobject.PARAM_READABLE)
    

    def prop_get_connected(self):
        return self._connected

    def prop_get_supported_pids(self):
        return self._supported_pids
       
    def prop_get_special_commands(self):
        return self._special_commands
        
    def prop_get_supported_commands(self):
        commands = self._special_commands.keys()
        for pid in self.supported_pids:
            commands.append(pid)
        return commands
        
    def prop_get_baudrate(self):
        if self._serial:
            return self._serial.baudrate
        else:
            return None

    def prop_get_port(self):
        if self._serial:
            return self._serial.port 
        else:
            return None
        

    def __init__(self):
        GObject.__init__(self)
        PropertyObject.__init__(self)

    ####################### Public Interface ###################
    
    def open(self, port):
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


class ELMDevice(OBDDevice, PropertyObject):
    """ This class talks to an ELM device. It sends commands and receives
        data from it.
    """
    __gtype_name__ = "ELMDevice"
    
    _special_commands = {
                        'voltage'   : ('atrv', 'V'),
                        'protocol'  : ('atdp', ''),
                        }
     
    
    def __init__(self, app):
        OBDDevice.__init__(self)
        PropertyObject.__init__(self)

        # TODO: ignore for the moment (see request_baudrate)
        # self._current_baudrate = self.initial_baudrate
        # self._requested_baudrate = None

        self.app = app
        self._connected = False
        self._serial = None
        self._watch_id = None
        
        self._supported_pids = []
        
        self._sent_command = None
        self._cleanup_command = True
        self._ret_cb = None
        self._err_cb = None
        self._cb_args = None

        self.app.prefs.register('device.port', '/dev/ttyUSB0')
        self.app.prefs.register('device.baudrate', 38400)
        self.app.prefs.register('device.ignore-keywords', False)

        fname = os.path.join(UI_DIR, 'device_prefs.ui')
        self.app.builder.add_from_file(fname)
        
        combo = self.app.builder.get_object('preference;combo;int;device.baudrate')
        cell = gtk.CellRendererText()
        combo.pack_start(cell, True)
        combo.add_attribute(cell, 'text', 0)
        
        self.app.prefs.add_dialog_page('device_prefs_vbox', _('Device'))
    

    def _send_command(self, command, ret, err, cleanup=True, *args):
        logger.debug('entering ELMDevice._send_command: %s' % command)
        if not self._serial.isOpen():
            raise OBDPortError('PortNotOpen', _('The port is not open'))

        self._cleanup_command = cleanup
        self._sent_command = command
        self._ret_cb = ret
        self._err_cb = err
        self._cb_args = args
        try:
            self._serial.flushOutput()
            self._serial.flushInput()
            self._serial.write(command)
            self._serial.write("\r")
        except serial.SerialException:
            self._sent_command = None
            self._ret_cb = None
            self._err_cb = None
            self._cb_args = None
            self.close()           
            raise OBDPortError('PortIOFailed', 
                               _('Unable to write to ') + self.port)         
            

    def _read_result(self):
        logger.debug('entering ELMDevice._read_result')
        timeout_count = 0
        try:
            buf = ''
            while timeout_count <= MAX_TIMEOUT:
                ch = self._serial.read(1)
                if ch == '':
                    timeout_count += 1
                if ch == '>': 
                    break
                else:
                    buf = buf + ch
            if buf == '':
                raise OBDPortError('PortIOFailed', 
                                   _('Read timeout from ') + self.port)
            buf = buf.replace('\r\r', '')
            return buf
            
        except serial.SerialException:
            raise OBDPortError('PortIOFailed', 
                               _('Unable to read from ') + self.port)
                                          
                
        return None
         
      
    def _parse_result(self, data):
        logger.debug('entering ELMDevice._parse_result: %s' % data)
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
                logger.debug('command sent, received >')
                error = True
                
            elif data[0] == '?':
                logger.debug('command sent, received ?')
                error = True
                msg = '?'

            elif 'ERROR' in data:
                logger.info('received ERROR')
                error = True
                msg = data
                
            elif 'SEARCHING' in data:
                logger.info('received SEARCHING: resending command')
                self._send_command(cmd, ret_cb, err_cb, args)

            elif 'BUS INIT' in data:
                logger.info('received BUS INIT: resending command')
                self._send_command(cmd, ret_cb, err_cb, args)
                
            elif 'UNABLE TO CONNECT' in data:
                logger.debug('received UNABLE TO CONNECT')
                error = True
                msg = 'UNABLE TO CONNECT'

            elif 'NO DATA' in data:
                logger.debug('received NO DATA')
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
                logger.debug('received >')
            else:
                logger.debug('no command sent, received %s' % data)
                

    def _port_io_watch_cb(self, fd, condition, data=None):
        logger.debug('entering ELMDevice._port_io_watch_cb')
        if condition & gobject.IO_HUP:
            logger.debug('received HUP signal')
            self._sent_command = None
            self._ret_cb = None
            self._err_cb = None
            self._cb_args = None
            self.close()    
            return False
        elif condition & gobject.IO_ERR:
            logger.debug('received ERR signal')
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
                logger.debug('CONDITION = IO_IN but reading times out. Error: %s' % e[0])
            finally:
                return True
        else:
            logger.debug('received an unknown io signal')
            return False

  
    
    def _read_supported_pids(self, modes=['09','01']):

        def success_cb(cmd, data, args):
            logger.debug('entering zero_success_cb')
            mode = cmd[:2]
            offset = int(cmd[2:4])
            self._supported_pids += decode_pids_from_bitstring(data, mode, offset)
            next = '%d' % (offset + 20)
            if mode + next in self._supported_pids:
                self._send_command(mode + next, success_cb, error_cb)
            else:
                if len(modes):
                    mode = modes.pop()
                    self._send_command(mode + '00', success_cb, error_cb)
                else:
                    logger.info('supported pids: %s\n' % self._supported_pids)
                    if not self._connected:
                        self._connected = True
                        self.emit('connected', True)
                    self.emit('supported-pids-changed')

        def error_cb(cmd, msg, args):
            logger.error('error reading supported pids, msg is: %s' % msg)
            raise OBDPortError('OpenPortFailed', 
                               _('could not read supported pids\n\n' + msg))

        if '01' in modes:
            self._supported_pids = []
        mode = modes.pop()
        self._send_command(mode + '00', success_cb, error_cb)
        
      
    def _initialize_device(self):
        def atz_success_cb(cmd, res, args):
            logger.debug('in atz_success_cb')
            if not 'ELM327' in res:
                logger.debug('invalid response')
                atz_error_cb(cmd, res, None)
            else:
                logger.debug('received answer valid')
                self._send_command('ate0', ate_success_cb, ate_error_cb)
            
        def atz_error_cb(cmd, msg, args):
            logger.debug('in atz_error_cb')
            raise OBDPortError('OpenPortFailed', 
                               _('atz command failed'))
            
        def ate_success_cb(cmd, res, args):
            logger.debug('in ate_success_cb')
            if not 'OK' in res:
                logger.debug('invalid response')
                ate_error_cb(cmd, res, args)
            else:
                if self.app.get('device.ignore-keywords'):
                    self._send_command('atkw0', atkw_success_cb, atkw_error_cb)
                else:
                    self._read_supported_pids()
            
        def ate_error_cb(cmd, msg, args):
            logger.debug('in atz_error_cb')
            raise OBDPortError('OpenPortFailed', 
                               _('ate0 command failed'))

        def atkw_success_cb(cmd, msg, args):
            logger.debug('in atkw_success_cb')
            if not 'OK' in res:
                logger.debug('invalid response')
                atkw_error_cb(cmd, res, args)
            else:
                self._read_supported_pids()            

        def atkw_error_cb(cmd, msg, args):
            logger.debug('in atkw_error_cb')
            raise OBDPortError('OpenPortFailed', 
                               _('atkw0 command failed'))
                               
        self._send_command('atz', atz_success_cb, atz_error_cb)                        
    
                               
                               
                                       
    ####################### Public Interface ###################
                
    def open(self):
        self._supported_pids = []
        port = self.app.prefs.get('device.port')
        baudrate = self.app.prefs.get('device.baudrate')
        
        try:
            self._serial = serial.Serial(port, baudrate, 
                                  serial.EIGHTBITS,
                                  serial.PARITY_NONE,
                                  serial.STOPBITS_ONE,
                                  timeout = 1)
        except serial.SerialException:
            raise OBDPortError('OpenPortFailed', 
                               _('Unable to open %s') % port)
        self._watch_id = gobject.io_add_watch(self._serial, 
              gobject.IO_IN | gobject.IO_PRI | gobject.IO_ERR | gobject.IO_HUP,
              self._port_io_watch_cb)                                  
        
        self._initialize_device()

        
    def close(self):
        """Resets the elm chip and closes the open serial port""" 
        self._supported_pids = []
        self._supported_freeze_frame_pids = None
        if self._serial:
            gobject.source_remove(self._watch_id)
            self._serial.close()
        self._connected = False
        self.emit('connected', False)
                   
    
    def read_pid_data(self, pid, ret_cb, err_cb, *args):
        def success_cb(cmd, data, args):
            ret = decode_result(data)
            ret_cb(cmd, ret, args)

        if self._serial and self._serial.isOpen():
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

        if self._serial and self._serial.isOpen():
            cmd = self._special_commands[command][0]
            self._send_command(cmd, success_cb, error_cb, args)
        else:
            raise OBDPortError('PortNotOpen', _('The port is not open'))              
       

    def read_command(self, command, ret_cb, err_cb, *args):
          
        if command in self._special_commands.keys():
            self.read_device_data(command, ret_cb, err_cb, args)
        else:
            self.read_pid_data(command, ret_cb, err_cb, args)

    
    
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
        
        if self._serial and self._serial.isOpen():
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

        if self._serial and self._serial.isOpen():
            self._send_command('04', success_cb, err_cb, args)
        else:
            raise OBDPortError('PortNotOpen', _('The port is not open'))                
                
                

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
    logger.debug('entering decode_result')
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
                logger.debug('we got back 7F which is an error')
            else:
                ret.append(data[4:])
        
    return ret
    
    
def decode_pids_from_bitstring(data, mode, offset, suffix=''):
    logger.debug('entering decode_pids_from_bitstring')
    pids = []
    decoded = decode_result(data)
    for item in decoded:
        bitstr = sensor.hex_to_bitstr(item)
        for i, bit in enumerate(bitstr):
            if bit == "1":
                pid = i + 1 + offset
                if pid < 16: 
                    pid_str = mode + '0' + hex(pid)[2:] + suffix
                else:
                    pid_str = mode + hex(pid)[2:] + suffix
                pids.append(pid_str.upper())
    return pids



