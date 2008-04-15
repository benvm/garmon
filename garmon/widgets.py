#!/usr/bin/python
#
# widgets.py
#
# Copyright (C) Ben Van Mechelen 2008 <me@benvm.be>
# 
# widgets.py is free software; you can redistribute it and/or modify
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
import gtk

import garmon
from garmon.property_object import PropertyObject, gproperty



class MILEntry(gtk.Entry):
    
    gproperty('on', bool, False)
    gproperty('on-color', str, '#F7D30D')
    gproperty('off-color', str, '#AAAAAA')
    
    def __init__(self):
        gtk.Entry.__init__(self, 3)
        PropertyObject.__init__(self)
        
    def __post_init__(self):
        self.connect('notify::on', self._notify_cb)
        self.connect('notify::on-color', self._notify_cb)
        self.connect('notify::off-color', self._notify_cb)
        
    def _notify_cb(self, o, pspec):
        if self.on:
            self.modify_base(gtk.STATE_NORMAL, gtk.gdk.color_parse(self.on_color))
        else:
            self.modify_base(gtk.STATE_NORMAL, gtk.gdk.color_parse(self.off_color))
    
     
