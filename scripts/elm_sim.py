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


import sys
import serial
import time

DEFAULT_PORT = '/dev/ttyUSB1'


commands = {'ATZ' : 'ELM327 v1.2',
            'ATE0' : 'OK',
            'ATRV' : '14.4V',
            'ATDP' : 'Some Protocol',
            'ATH0' : 'OK',
            'ATH1' : 'OK',
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
            '0114' : '41 14 55 99',
            '0115' : '41 15 55 98',
            '0116' : '41 16 55 99',
            '0117' : '41 17 55 98',
            '0118' : '41 18 55 99',
            '0119' : '41 19 55 98',
            '011A' : '41 1A 55 99',
            '011B' : '41 1B 55 97',
            '011C' : '41 1C 06',
            '011D' : '41 1D 45',
            '011E' : '41 1E 80',
            '011F' : '41 1F 45 78',
            '0120' : '41 20 00180000',
            '012C' : '41 2C 97',
            '012D' : '41 2C AA',
            '03' : '43 07 04 06 34 05 23',
            '04' : '44',
            '0200' : '42 00 FFFFFFFF',
            '0220' : '42 00 00000000',
            '0201' : '42 01 82 07 65 04',
            '0202' : '42 02 01 67',
            '0203' : '42 03 02 04',
            '0204' : '42 04 99',
            '0205' : '42 05 88',
            '0206' : '42 06 99',
            '0207' : '42 07 88',
            '0208' : '42 08 AA',
            '0209' : '42 09 AB',
            '020A' : '42 0A 56',
            '020B' : '42 0B 50',
            '020C' : '42 0C 55 44',
            '020D' : '42 0D 78',
            '020E' : '42 0E 70',
            '020F' : '42 0F 36',
            '0210' : '42 10 75 A6',
            '0211' : '42 11 26',
            '0212' : '42 12 01',
            '0213' : '42 13 88',
            '0214' : '42 14 55 AA',
            '0215' : '42 15 55 BA',
            '0216' : '42 16 55 BB',
            '0217' : '42 17 55 AB',
            '0218' : '42 18 55 AC',
            '0219' : '42 19 55 A3',
            '021A' : '42 1A 55 B3',
            '021B' : '42 1B 55 AA',
            '021C' : '42 1C 06',
            '021D' : '42 1D 45',
            '021E' : '42 1E 80',
            '021F' : '42 1F 45 78',
            '0900' : '49 00 C000000',
                        
                     }
                      
alternate_commands = {'ATZ' : 'ELM327 v1.2',
            'ATE0' : 'OK',
            'ATRV' : '12.4V',
            'ATDP' : 'Some Protocol',
            'ATH0' : 'OK',
            'ATH1' : 'OK',
            '0100' : '41 00 FFFFFFFF',
            '0120' : '41 00 00180000',
            '0101' : '41 01 82 07 65 04',
            '0102' : '41 02 00 00',
            '0103' : '41 03 02 04',
            '0104' : '41 04 77',
            '0105' : '41 05 66',
            '0106' : '41 06 45',
            '0107' : '41 07 66',
            '0108' : '41 08 55',
            '0109' : '41 09 BA',
            '010A' : '41 0A 99',
            '010B' : '41 0B 99',
            '010C' : '41 0C 44 55',
            '010D' : '41 0D 65',
            '010E' : '41 0E 60',
            '010F' : '41 0F 77',
            '0110' : '41 10 66 99',
            '0111' : '41 11 45',
            '0112' : '41 12 22',
            '0113' : '41 13 55',
            '0114' : '41 14 55 AA',
            '0115' : '41 15 55 AB',
            '0116' : '41 16 55 AA',
            '0117' : '41 17 55 AC',
            '0118' : '41 18 55 A9',
            '0119' : '41 19 55 AA',
            '011A' : '41 1A 55 AB',
            '011B' : '41 1B 55 AA',
            '011C' : '41 1C 06',
            '011D' : '41 1D 23',
            '011E' : '41 1E 80',
            '011F' : '41 1F 34 56',
            '012C' : '41 2C 55',
            '012D' : '41 2C BB',
            '03' : '43 05 35 03 23 03 34',
            '04' : '44',
            '0900' : '49 00 C0000000',
                        
                     }                  

class ElmSimulator(object):
    def __init__(self, port, baudrate=9600, 
                         size=serial.EIGHTBITS, 
                         parity=serial.PARITY_NONE, 
                         stopbits=serial.STOPBITS_ONE ):
        
        try:
            print 'Opening serial port'
            self.port = serial.Serial(port, 
                                        baudrate, 
                                        size,
                                        parity,
                                        stopbits,
                                        timeout = 0)
                                                
        
        except serial.SerialException, e:
            print 'Failed to open serial port: %s: %s' % (port, e) 
            
            
    def start(self):
        
        alternate = False

        if not self.port:
            print 'No serial port open'
            return
        print 'Start listening'
        while True:
            buf = ""
            while True:
                ch = self.port.read(1)
                if ch == '\r' and len(buf) > 0:
                    break
                else:
                    buf = buf + ch
                        
            print 'received %s' % buf
            buf = buf.upper()
            
            self.port.flushOutput()
            self.port.flushInput()

            time.sleep(1)
            if commands.has_key(buf):
                if buf[:2] == '02':
                    ret = commands[buf]
                else:
                    if alternate:
                        ret = alternate_commands[buf]
                    else:
                        ret = commands[buf]
                    alternate = not alternate

                print 'sending %s' % ret
                if not ret == 'Nothing':
                    self.port.write(ret + '\r\r>')
                    
            else:
                print 'unknown command'
                self.port.write('?\r\r>')



if __name__ == "__main__":
    try:
        port = sys.argv[1]
    except IndexError:
        print 'No port specified'
        port = DEFAULT_PORT
    print 'trying port: %s' % port
    try:
        sim = ElmSimulator(port)
    except:
        sys.exit(2)
    sim.start()

