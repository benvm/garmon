#!/usr/bin/python
#
# dtc_reader.py
#
# Copyright (C) Ben Van Mechelen 2007-2008 <me@benvm.be>
# 
# dtc_reader.py.py is free software; you can redistribute it and/or modify
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

import os

import gobject
from gobject import GObject
import gtk
from gtk import glade
from gettext import gettext as _

import garmon
import garmon.plugin

from garmon.plugin import Plugin, STATUS_STOP, STATUS_WORKING, STATUS_PAUSE
from garmon.property_object import PropertyObject, gproperty
from garmon.obd_device import OBDDataError, OBDPortError
from garmon.trouble_codes import DTC_CODES, DTC_CODE_CLASSES

__name = _('DTC Reader')
__version = '0.1'
__author = 'Ben Van Mechelen'
__description = _('Reads the stored trouble codes from the vehicle')
__class = 'DTCReader'


(
    COLUMN_CODE,
    COLUMN_DTC,
    COLUMN_DESC
) = range(3)


class DTCReader (Plugin, gtk.VBox):

    def __init__(self, app):
        gtk.VBox.__init__(self)
        
        self.app = app
        self.dir = os.path.dirname(__file__)
        self.status = STATUS_STOP
        
        file = os.path.join(self.dir, 'dtc_reader.glade')
        self._glade = glade.XML(file, 'hpaned')

        self._dtc_info = DTCInfo(self._glade)
        
        hpaned = self._glade.get_widget('hpaned')
        self.pack_start(hpaned, True, True)
        hpaned.set_border_width(5)

        dtc_frame = self._glade.get_widget('dtc_frame')


        self.treemodel = gtk.ListStore(gobject.TYPE_STRING,
                                                        gobject.TYPE_STRING,
                                                        gobject.TYPE_STRING)
        treeview = gtk.TreeView(self.treemodel)
        treeview.set_rules_hint(True)
        column = gtk.TreeViewColumn(_('Bits'), gtk.CellRendererText(),
                                    text=COLUMN_CODE)
        treeview.append_column(column)
        column = gtk.TreeViewColumn(_('DTC'), gtk.CellRendererText(),
                                    text=COLUMN_DTC)
        treeview.append_column(column)
        
        selection = treeview.get_selection()
        selection.set_mode(gtk.SELECTION_SINGLE)
        selection.connect("changed", self._on_selection_changed)

        dtc_frame.add(treeview)
        
        self.show_all()
        
        app.connect("reset", self._on_reset)
        app.notebook.connect('switch-page', self._notebook_page_change_cb)
        

    def _on_reset(self, garmon):
        self.start()
        

    def _on_selection_changed(self, selection):
        treeview = selection.get_tree_view()
        model, iter = selection.get_selected()
        
        if iter:
            dtc = model.get_value(iter, COLUMN_DTC)
            cls = DTC_CODE_CLASSES[dtc[:3]]
            description = DTC_CODES[dtc]
            additional = 'Coming soon'
        else:
            dtc = cls = description = additional = ''
            
        self._dtc_info.code = dtc
        self._dtc_info.code_class = cls
        self._dtc_info.description = description
        self._dtc_info.additional = additional


    def _notebook_page_change_cb (self, notebook, no_use, page):
        plugin = notebook.get_nth_page(page)
        if plugin is self:
            self.start()


    def start(self):
        self.treemodel.clear()
        self.app.scheduler.working = False
        if self.app.obd:
            try:
                dtcs = self.app.obd.get_dtc()
                for item in dtcs:
                    code = item
                    dtc = decode_dtc_code(item)
                    desc = DTC_CODES[dtc]
                    iter = self.treemodel.append(None)
                    self.treemodel.set(iter, COLUMN_CODE, code,
                                             COLUMN_DTC, dtc,
                                             COLUMN_DESC, desc)
            except OBDPortError, e:
                self._display_port_error_dialog(e)
                return


    def load(self):
        self.app.notebook.append_page(self, gtk.Label(_('DTC Reader')))
                
                
    def unload(self):
        self.app.notebook.remove(self)
        

class DTCInfo(GObject, PropertyObject) :


    gproperty('code', str)
    gproperty('code-class', str)
    gproperty('description', str)
    gproperty('additional', str)


    def __init__(self, glade):
        GObject.__init__(self)
        PropertyObject.__init__(self)

        self._code_label = glade.get_widget('code_label')
        self._class_label = glade.get_widget('class_label')
        self._description_label = glade.get_widget('description_label')
        self._additional_textview = glade.get_widget('additional_textview')
    
        self._additional_buffer = gtk.TextBuffer()
        self._additional_textview.set_buffer(self._additional_buffer)

    def __post_init__(self):
        self.connect('notify::code', self._notify_cb)
        self.connect('notify::code-class', self._notify_cb)
        self.connect('notify::description', self._notify_cb)
        self.connect('notify::additional', self._notify_cb)
        
        
    def _notify_cb(self, o, pspec):
        if pspec.name == 'code':
            self._code_label.set_text(self.code)
        elif pspec.name == 'code-class':
            self._class_label.set_text(self.code_class)
        elif pspec.name == 'description':
            self._description_label.set_text(self.description)
        elif pspec.name == 'additional':
            self._additional_buffer.set_text(self.additional)
        


def decode_dtc_code(code):
    if not code.__len__() == 4:
        return 'ERROR'
        
    FIRST_BIT = ('P', 'C', 'B', 'U')
    SECOND_BIT =('0', '1', '2', '3')
    
    result = FIRST_BIT[eval('0x%s' % code[0]) & 0xC]
    result += SECOND_BIT[eval('0x%s' % code[0]) & 0x3]
    result += code[1:]
    
    return result


    