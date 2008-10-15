#!/usr/bin/python
# -*- coding: iso-8859-15 -*-
#
# sensor.py
#
# Copyright (C) Ben Van Mechelen 2007-2008 <me@benvm.be>
# 
# sensor.py is free software; you can redistribute it and/or modify
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
from gobject import GObject

import garmon
from garmon.property_object import PropertyObject, gproperty, gsignal


class Command (GObject, PropertyObject):
    __gtype_name__ = 'Command'
    
    gproperty('command', str, flags=gobject.PARAM_READABLE)
    gproperty('data', object)

    gsignal('data-changed', object)
    
    def __init__(self, command):
        GObject.__init__(self)
        PropertyObject.__init__(self, command=command)
    
    def __post_init__(self):
        self.connect('notify::data', self._notify_data_cb)
        
    def _notify_data_cb(self, o, pspec):
        self.emit('data-changed', self.data)
        
    def clear(self):
        self.data = None


class Sensor (Command, PropertyObject):
    __gtype_name__ = 'Sensor'

    gproperty('index', int, 0)
    gproperty('indices', int)   
    gproperty('name', str, flags=gobject.PARAM_READABLE)
    gproperty('metric_value', str, flags=gobject.PARAM_READABLE)
    gproperty('metric_units', str, flags=gobject.PARAM_READABLE)
    gproperty('imperial_value', str, flags=gobject.PARAM_READABLE)
    gproperty('imperial_units', str, flags=gobject.PARAM_READABLE)    

    def prop_set_index(self, index):
        if self._indices < index+1:
            raise ValueError, 'index too high'
        else:
            return index
            
    def prop_get_indices(self):
        return self._num_values
           
    def prop_get_metric_value(self):
        if self.data:
            return self._decoder(self.data)[0]
        else:
            return None            
               
    def prop_get_imperial_value(self):
        if self.data:
            return self._decoder(self.data)[1]
        else:
            return None  
            
    def prop_get_metric_units(self):
        return self._metric_units
        
    def prop_get_imperial_units(self):
        return self._imperial_units             
            
    def prop_get_name(self):
        return self._name    


    def __init__(self, command, index=0, units='Metric'):
        self._indices = len(SENSORS[command[2:]])
        self._imperial_units = None
        self._metric_units = None
        self._decoder = None
        Command.__init__(self, command)
        PropertyObject.__init__(self, command=command, index=index)

    def __post_init__(self):
        Command.__post_init__(self)
        self.connect('notify::index', self._index_changed_cb)
        self._update_info()
      
    def _update_info(self):
        self._name = SENSORS[self.command[2:]][self.index][NAME]
        self._metric_units = SENSORS[self.command[2:]][self.index][METRIC]
        self._imperial_units = SENSORS[self.command[2:]][self.index][IMPERIAL]       
        self._decoder = SENSORS[self.command[2:]][self.index][FUNC]
        
    def _index_changed_cb(self, o, pspec):
        self._clear_data()
        self._update_info()
           
          
class StateMixin (object):
    
    gproperty('active', bool, False)
    gproperty('supported', bool, False) 
    
    gsignal('active-changed', bool)
    
    
    
class UnitMixin (object):
    gproperty('unit-standard', str, 'Metric')

    def prop_set_unit_standard(self, standard):
        if not standard in ('Metric', 'Imperial'):
            raise ValueError, 'unit-standard should be either Metric or Imperial'
        return standard
      
        
def num_values(pid):
    return len(SENSORS[pid])


def dtc_decode_num(code):
    num = eval ("0x%s" % code[1])
    return (num, num)


def dtc_decode_mil(code):
    num = eval ("0x%s" % code[0])
    if num & 8:
        mil = 'On'
    else:
        mil = 'Off'
    return (mil, mil)


def hex_to_bitstr(str):
    """ Converts a hex value into a bitstring."""

    bitstr = ""
    for i in str:
        hex = eval("0x%s" % i)
        for bit in [8,4,2,1]:
            if hex & bit :
                bitstr += '1'
            else:
                bitstr += '0'
    return bitstr


def bitstring(data):
    value = hex_to_bitstr(data)
    return (value, value)


def no_op(data):
    return (data, data)


def percent(data):
    value = eval("0x%s" % data) * 100 / 255
    return (value, value)


def egr_error(data):
    value = eval("0x%s" % data)
    value = int(round(value * 0.78125 - 100))
    return (value, value)


def fuel_percent(data):
    value = eval("0x%s" % data)
    value = round((value - 128) * 0.78125)
    return (value, value)


def o2_voltage(data):
    value = eval("0x%s" % data[:2])
    value = value * 0.005
    return (value, value)


def o2_fuel_percent(data):
    value = eval("0x%s" % data[2:])
    if value != 255:
        value = round((value - 128) * 0.78125)
    return (value, value)


def fuel_pres(data):
    value = eval("0x%s" % data)
    metric = value * 3
    imperial = round(metric * 0.14504, 1)
    return (metric, imperial)


def secs_to_mins(data):
    value = eval("0x%s" % data) / 60
    return (value, value)

def todo(data):
    return (data, data)


def intake_pres(data):
    value = eval("0x%s" % data)
    metric = value
    imperial = round(metric * 0.14504, 1)
    return (metric, imperial)


def rpm(data):
    A = eval("0x%s" % data[:2])
    B = eval("0x%s" % data[2:])
    data = ((A * 256) + B) / 4
    return (data, data)


def speed(data):
    metric = eval("0x%s" % data)
    imperial = int(metric * 0.621)
    return (metric, imperial)

def timing_adv(data):
    value = eval("0x%s" % data)
    value = value / 2 - 64
    return (value, value)

def maf(data):
    A = eval("0x%s" % data[:2])
    B = eval("0x%s" % data[2:])
    metric = ((256 * A) + B) / 100
    imperial = round(metric * 0.1323, 1)
    return (metric, imperial)

def temp(data):
    value = eval("0x%s" % data)
    metric = value - 40
    imperial = metric * 9 / 5 + 32
    return (metric, imperial)

def fuel_status_1(data):
    return fuel_status(eval('0x%s' % data[:2]))

def fuel_status_2(data):
    return fuel_status(eval('0x%s' % data[2:]))
    
def fuel_status(data):
    ret = 'Not In Use'
    for bit in range(len(FUEL_STATUS)):
        if data & 1 << bit:
            ret = (FUEL_STATUS[bit]) 
    return (ret, ret)

def sec_air_status(data):
    data = eval('0x%s' % data)
    ret = 'Not In Use'
    for bit in range(len(AIR_STATUS)):
        if data & 1 << bit:
            ret = (AIR_STATUS[bit])
    return (ret, ret)

def obd_designation(data):
    ret = OBD_DESIGNATIONS[data[:2]]
    return (ret, ret)
    

def decode_dtc_code(code):
    if not code:
        return
    if not len(code) == 4:
        return 'ERROR'
        
    CLASS_LETTER = ('P', 'C', 'B', 'U')
    CLASS_NUMBER =('0', '1', '2', '3')
    
    result = CLASS_LETTER[(eval('0x%s' % code[0]) & 0xC) >> 2]
    result += CLASS_NUMBER[eval('0x%s' % code[0]) & 0x3]
    result += code[1:]
    
    return result
    

FUEL_STATUS = [
    _('Open Loop'),
    _('Closed Loop'),
    _('Open Loop - Caused by driving conditions'),
    _('Open Loop - Caused by system fault'),
    _('Closed Loop - But there is a fault'),
    ]

 
AIR_STATUS = [
    _('Upstream of first Catalytic convertor.'),
    _('Downstream of first Catalytic convertor inlet.'),
    _('Atmosphere/off'),
    ]

OBD_DESIGNATIONS = {
'01' : _('OBD II (California ARB)'),
'02' : _('OBD (Federal EPA)'),
'03' : _('OBD and OBD II'),
'04' : _('OBD I'),
'05' : _('Not intended to meet any OBD requirements.'),
'06' : _('EOBD (Europe)'),
}   


(   NAME, 
    FUNC, 
    METRIC, 
    IMPERIAL
 ) = range(4) 
 


SENSORS = {#  PID               Name                            formula                        unit
           #                                                                             metric     imperial          
            "00": ((_("Supported PIDs"),                     bitstring,              "",         ""          ),),    
            "01": ((_("Number of trouble codes"),            dtc_decode_num,         "",         ""          ),
                   (_("Malfunction Indicator Light"),        dtc_decode_mil,         "",         ""          )),    
            "02": ((_("DTC Causing Freeze Frame"),           no_op,                  "",         ""          ),),    
            "03": ((_("Fuel System Status 1"),               fuel_status_1,          "",         ""          ),
                   (_("Fuel System Status 2"),               fuel_status_2,          "",         ""          ),),
            "04": ((_("Calculated Engine Load Value"),       percent,                "%",        "%"         ),),
            "05": ((_("Engine coolant temperature"),         temp,                   "°C",       "F"         ),),
            "06": ((_("Short Term Fuel Trim - Bank 1"),      fuel_percent,           "%",        "%"         ),),
            "07": ((_("Long Term Fuel Trim - Bank 1"),       fuel_percent,           "%",        "%"         ),),
            "08": ((_("Short Term Fuel Trim - Bank 2"),      fuel_percent,           "%",        "%"         ),),
            "09": ((_("Long Term Fuel Trim - Bank 2"),       fuel_percent,           "%",        "%"         ),),
            "0A": ((_("Fuel Pressure"),                      fuel_pres,              "kPa",      "psi"       ),),
            "0B": ((_("Intake Manifold Pressure"),           intake_pres,            "kPa",      "psi"       ),),
            "0C": ((_("Engine RPM"),                         rpm,                    "rpm",      "rpm"       ),),
            "0D": ((_("Vehicle Speed"),                      speed,                  "km/h",     "MPH"       ),),
            "0E": ((_("Timing Advance"),                     timing_adv,             "°",        "°"         ),),
            "0F": ((_("Intake Air Temp"),                    temp,                   "°C",       "F"         ),),
            "10": ((_("MAF Air Flow Rate"),                  maf,                    "g/s",      "lb/min"    ),),
            "11": ((_("Throttle Position"),                  percent,                "%",        "%"         ),),
            "12": ((_("Secondary Air Status"),               sec_air_status,         "",         ""          ),),
            "13": ((_("O2 Sensors present"),                 bitstring,              "",         ""          ),),
            "14": ((_("O2 Sensor: 1 - 1 Voltage"),           o2_voltage,             "V",        "V"         ),
                   (_("O2 Sensor: 1 - 1 Fuel Trim"),         o2_fuel_percent,        "%",        "%"         )),
            "15": ((_("O2 Sensor: 1 - 2 Voltage"),           o2_voltage,             "V",        "V"         ),
                   (_("O2 Sensor: 1 - 2 Fuel Trim"),         o2_fuel_percent,        "%",        "%"         )),
            "16": ((_("O2 Sensor: 1 - 3 Voltage"),           o2_voltage,             "V",        "V"         ),
                   (_("O2 Sensor: 1 - 3 Fuel Trim"),         o2_fuel_percent,        "%",        "%"         )),
            "17": ((_("O2 Sensor: 1 - 4 Voltage"),           o2_voltage,             "V",        "V"         ),
                   (_("O2 Sensor: 1 - 4 Fuel Trim"),         o2_fuel_percent,        "%",        "%"         )),
            "18": ((_("O2 Sensor: 2 - 1 Voltage"),           o2_voltage,             "V",        "V"         ),
                   (_("O2 Sensor: 2 - 1 Fuel Trim"),         o2_fuel_percent,        "%",        "%"         )),
            "19": ((_("O2 Sensor: 2 - 2 Voltage"),           o2_voltage,             "V",        "V"         ),
                   (_("O2 Sensor: 2 - 2 Fuel Trim"),         o2_fuel_percent,        "%",        "%"         )),
            "1A": ((_("O2 Sensor: 2 - 3 Voltage"),           o2_voltage,             "V",        "V"         ),
                   (_("O2 Sensor: 2 - 3 Fuel Trim"),         o2_fuel_percent,        "%",        "%"         )),
            "1B": ((_("O2 Sensor: 2 - 4 Voltage"),           o2_voltage,             "V",        "V"         ),
                   (_("O2 Sensor: 2 - 4 Fuel Trim"),         o2_fuel_percent,        "%",        "%"         )),
            "1C": ((_("OBD Designation"),                    obd_designation,        "",         ""          ),),
            "1D": ((_("O2 Sensors present"),                 bitstring,              "",         ""          ),),
            "1E": ((_("Aux input status"),                   no_op,                  "",         ""          ),),
            "1F": ((_("Time Since Engine Start"),            secs_to_mins,           "min",      "min"       ),),
            "20": ((_("Supported PIDs"),                     bitstring,              "",         ""          ),),
            "21": ((_("Distance traveled with MIL on"),      todo,                   "km",       "Miles"     ),),
            "22": ((_("Fuel Rail Pressure ") +
                    _("(relative to manifold vacuum)"),      todo,                   "kPa",      "psi"       ),),
            "23": ((_("Fuel Rail Pressure (diesel)"),        todo,                   "kPa",      "psi"       ),),
            "24": ((_("02S1_WR_Lambda"),                     todo,                   "λ",        "λ"         ),),
            "25": ((_("02S2_WR_Lambda"),                     todo,                   "λ",        "λ"         ),),
            "26": ((_("02S3_WR_Lambda"),                     todo,                   "λ",        "λ"         ),),
            "27": ((_("02S4_WR_Lambda"),                     todo,                   "λ",        "λ"         ),),
            "28": ((_("02S5_WR_Lambda"),                     todo,                   "λ",        "λ"         ),),
            "29": ((_("02S6_WR_Lambda"),                     todo,                   "λ",        "λ"         ),),
            "2A": ((_("02S7_WR_Lambda"),                     todo,                   "λ",        "λ"         ),),
            "2B": ((_("02S8_WR_Lambda"),                     todo,                   "λ",        "λ"         ),),
            "2C": ((_("Commanded EGR"),                      percent,                "%",        "%"         ),),
            "2D": ((_("EGR Error"),                          egr_error,              "%",        "%"         ),),
    }
"""    




01  2E  1   Commanded evaporative purge     0   100      %  100*A/255
01  2F  1   Fuel Level Input    0   100      %  100*A/255
01  30  1   # of warm-ups since codes cleared   0   255     N/A     A
01  31  2   Distance traveled since codes cleared   0   65,535  km  (A*256)+B
01  32  2   Evap. System Vapor Pressure     -8,192  8,192   Pa  ((A*256)+B)/4 - 8,192
01  33  1   Barometric pressure     0   255     kPa (Absolute)  A
01  34  4   O2S1_WR_lambda(1):
Equivalence Ratio
Current     0
-128    2
128     N/A
mA  ((A*256)+B)*0.0000305
((C*256)+D)*0.00391 - 128
01  35  4   O2S2_WR_lambda(1):
Equivalence Ratio
Current     0
-128    2
128     N/A
mA  ((A*256)+B)*0.0000305
((C*256)+D)*0.00391 - 128
01  36  4   O2S3_WR_lambda(1):
Equivalence Ratio
Current     0
-128    2
128     N/A
mA  ((A*256)+B)*0.0000305
((C*256)+D)*0.00391 - 128
01  37  4   O2S4_WR_lambda(1):
Equivalence Ratio
Current     0
-128    2
128     N/A
mA  ((A*256)+B)*0.0000305
((C*256)+D)*0.00391 - 128
01  38  4   O2S5_WR_lambda(1):
Equivalence Ratio
Current     0
-128    2
128     N/A
mA  ((A*256)+B)*0.0000305
((C*256)+D)*0.00391 - 128
01  39  4   O2S6_WR_lambda(1):
Equivalence Ratio
Current     0
-128    2
128     N/A
mA  ((A*256)+B)*0.0000305
((C*256)+D)*0.00391 - 128
01  3A  4   O2S7_WR_lambda(1):
Equivalence Ratio
Current     0
-128    2
128     N/A
mA  ((A*256)+B)*0.0000305
((C*256)+D)*0.00391 - 128
01  3B  4   O2S8_WR_lambda(1):
Equivalence Ratio
Current     0
-128    2
128     N/A
mA  ((A*256)+B)*0.0000305
((C*256)+D)*0.00391 - 128
01  3C  2   Catalyst Temperature
Bank 1, Sensor 1    -40     6,513.5     °C     ((A*256)+B)/10 -40
01  3D  2   Catalyst Temperature
Bank 2, Sensor 1    -40     6,513.5     °C     ((A*256)+B)/10 -40
01  3E  2   Catalyst Temperature
Bank 1, Sensor 2    -40     6,513.5     °C     ((A*256)+B)/10 -40
01  3F  2   Catalyst Temperature
Bank 2, Sensor 2    -40     6,513.5     °C     ((A*256)+B)/10 -40
01  40  4   PIDs supported 41-60 (?)                Bit encoded [A7..D0] == [PID 0x41..PID 0x60] (?)
01  41   ?  Monitor status this drive cycle      ?   ?   ?   ?
01  42  2   Control module voltage  0   65.535  V   ((A*256)+B)/1000
01  43  2   Absolute load value     0   25696    %  ((A*256)+B)*100/255
01  44  2   Command equivalence ratio   0   2   N/A     ((A*256)+B)*0.0000305
01  45  1   Relative throttle position  0   100      %  A*100/255
01  46  1   Ambient air temperature     -40     215     °C     A-40
01  47  1   Absolute throttle position B    0   100      %  A*100/255
01  48  1   Absolute throttle position C    0   100      %  A*100/255
01  49  1   Accelerator pedal position D    0   100      %  A*100/255
01  4A  1   Accelerator pedal position E    0   100      %  A*100/255
01  4B  1   Accelerator pedal position F    0   100      %  A*100/255
01  4C  1   Commanded throttle actuator     0   100      %  A*100/255
01  4D  2   Time run with MIL on    0   65,535  minutes     (A*256)+B
01  4E  2   Time since trouble codes cleared    0   65,535  minutes     (A*256)+B
01  C3   ?   ?   ?   ?   ?  Returns numerous data, including Drive Condition ID and Engine Speed*
01  C4   ?   ?   ?   ?   ?  B5 is Engine Idle Request
B6 is Engine Stop Request*
"""

   
if __name__ == '__main__':
    print 'testing OBDData'
    s = OBDSensor('0114')
    print s.pid
    print s.index
    print s.data
    s.data = '78'
    print s.value

    
