#!/usr/bin/python
#
# plugin.py
#
# Copyright (C) Ben Van Mechelen 2007-2008 <me@benvm.be>
# 
# plugin.py is free software.
# 
# You may redistribute it and/or modify it under the terms of the
# GNU General Public License, as published by the Free Software
# Foundation; either version 2 of the License, or (at your option)
# any later version.
# 
# plugin.py is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with plugin.py.  If not, write to:
#   The Free Software Foundation, Inc.,
#   51 Franklin Street, Fifth Floor
#   Boston, MA  02110-1301, USA.


import gobject
import gtk

from gettext import gettext as _

(
    STATUS_WORKING,
    STATUS_STOP,
    STATUS_PAUSE
)  = range(3)


class Plugin(object):
    ui_info = ''
    action_group = None
    merge_id = None

    def _display_port_error_dialog(self, error):
            err, msg = error
            self.stop()
            dialog = gtk.MessageDialog(self.app, gtk.DIALOG_DESTROY_WITH_PARENT,
                                                    gtk.MESSAGE_WARNING, gtk.BUTTONS_YES_NO,
                                                    err + '\n\n' + msg + '\n\n' + 
                                                    _("Please make sure the device is connected.")
                                                    + '\n\n\n' + _('Should we attempt a reset?'))
            dialog.connect('response', self._port_error_dialog_response)
            dialog.run()
            
            
            
    def _port_error_dialog_response(self, dialog, response):
        dialog.destroy()
        if response == gtk.RESPONSE_YES:
            self.app.reset()
   
