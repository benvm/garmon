#!/usr/bin/python
#
# elm_sim.py
#
# Copyright (C) Ben Van Mechelen 2007 <me@benvm.be>
# 
# elm_sim.py is free software; you can redistribute it and/or modify
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


import serial


commands = {'atz' : 'ELM327 v1.2',
            'ate0' : 'OK',
            'atrv' : '12.4V',
            'atdp' : 'Some Protocol',
            '0100' : '41 00 FFFFFFFF',
            '0120' : '41 00 00000000',
            '0101' : '41 01 82 07 65 04',
            '0102' : '41 02 00 00',
            '0103' : '41 03 02 04',
            '0104' : '41 04 99',
            '0105' : '41 05 88',
            '0106' : '41 06 99',
            '0107' : '41 07 88',
            '0108' : '41 08 AA',
            '0109' : '41 09 AB',
            '010A' : '41 0A 56',
            '010B' : '41 0B 50',
            '010C' : '41 0C 55 44',
            '010D' : '41 0D 78',
            '010E' : '41 0E 70',
            '010F' : '41 0F 36',
            '0110' : '41 10 75 A6',
            '0111' : '41 11 26',
            '0112' : '41 12 01',
            '0113' : '41 13 88',
            '0114' : '41 14 55 66',
            '0115' : '41 15 55 66',
            '0116' : '41 16 55 66',
            '0117' : '41 17 55 66',
            '0118' : '41 18 55 66',
            '0119' : '41 19 55 66',
            '011A' : '41 1A 55 66',
            '011B' : '41 1B 55 66',
            '011C' : '41 1C 06',
            '011D' : '41 1D 45',
            '011E' : '41 1E 80',
            '011F' : '41 1F 45 78',
            '03' : '43 01 00 01 01 00 00',
            '04' : '44',
                        
                     }
                                        

class ElmSimulator(object):
    def __init__(self, port, baudrate=9600, 
                         size=serial.EIGHTBITS, 
                         parity=serial.PARITY_NONE, 
                         stopbits=serial.STOPBITS_ONE ):
        
        try:
        
            self.port = serial.Serial(port, 
                                        baudrate, 
                                        size,
                                        parity,
                                        stopbits,
                                        timeout = 0)
                                                
        
        except serial.SerialException, e:
            print 'Failed to open serial port: %s' % port
            print e
            
            
    def start(self):
        if not self.port:
            print 'No serial port open'
            return
            
        while True:
            buf = ""
            while True:
                ch = self.port.read(1)
                if ch == '\r' and len(buf) > 0:
                    break
                else:
                    buf = buf + ch
                        
            print 'received %s' % buf
            
            self.port.flushOutput()
            self.port.flushInput()
            
            if commands.has_key(buf):
                ret = commands[buf]
                print 'sending %s' % ret
                if not ret == 'Nothing':
                    self.port.write(ret + '\r\r>')
                    
            else:
                print 'unknown command'
                self.port.write('?\r\r>')
                
                
if __name__ == "__main__":
    sim = ElmSimulator('/dev/ttyUSB1')
    sim.start()
    
    
        
        
    
            
