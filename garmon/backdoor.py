#!/usr/bin/python
#
# backdoor.py
#
# Copyright (C) Ben Van Mechelen 2008-2009 <me@benvm.be>
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
import gobject
import gtk

from pyconsole import Console


class BackDoor (gtk.ScrolledWindow) :
    def __init__(self, garmon):
        gtk.ScrolledWindow.__init__(self)
        
        console = Console(locals=dict(garmon=garmon),
                            banner=_("Python Shell. Inspect Garmons internals."),
                            use_rlcompleter=False)
        self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.add(console)
        self.show_all()



