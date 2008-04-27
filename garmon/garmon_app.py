#!/usr/bin/python
#
# garmon.py
#
# Copyright (C) Ben Van Mechelen 2007-2008 <me@benvm.be>

gpl = """
                      GNU General Public License
                
Garmon is free software.
 
You may redistribute it and/or modify it under the terms of the
GNU General Public License, as published by the Free Software
Foundation; either version 2 of the License, or (at your option)
any later version.

Garmon is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with main.py.  If not, write to:
  The Free Software Foundation, Inc.,
  51 Franklin Street, Fifth Floor
  Boston, MA  02110-1301, USA.
"""

import gobject
import gtk
from gtk import glade
import gconf
import locale
import gettext
import os

# set up gettext for translations
locale.setlocale(locale.LC_ALL, '')
from gettext import gettext as _
gettext.textdomain('garmon')
gtk.glade.textdomain('garmon')

import garmon
from garmon import GLADE_DIR

import garmon.plugin_manager as plugin_manager

from garmon.prefs import PreferenceManager
from garmon.obd_device import OBDDevice, OBDError, OBDDataError, OBDPortError
from garmon.scheduler import Scheduler
from garmon.property_object import PropertyObject, gproperty, gsignal
from garmon.backdoor import BackDoor

ui_info = \
'''<ui>
  <menubar name='MenuBar'>
    <menu action='FileMenu'>
      <menuitem action='Quit'/>
    </menu>
    <menu action='EditMenu'>
      <menuitem action='Preferences'/>
      <separator/>
      <menuitem action='Plugins'/>
    </menu>
    <menu action='DeviceMenu'>
      <menuitem action='Reset'/>
      <menuitem action='Monitor'/>
      <separator/>
    <placeholder name='DeviceMenuItems'/>
    </menu>
    <menu action='ViewMenu'>
      <menuitem action='FullScreen'/>
      <menuitem action='PythonShell'/>
    </menu>    
    <menu action='HelpMenu'>
      <menuitem action='About'/>
    </menu>
  </menubar>
  <toolbar  name='ToolBar'>
    <toolitem action='Reset'/>
    <toolitem action='Monitor'/>
    <separator/>
    <placeholder name='DeviceToolItems'/>
    <separator/>
    <toolitem action='Preferences'/>
    <separator/>
    <toolitem action='FullScreen'/>
    <separator/>
    <toolitem action='Quit'/>
  </toolbar>
</ui>'''


(   PAGE_SENSORS,
    PAGE_DTC
) = range(2)

    
class GarmonApp(gtk.Window, PropertyObject):
    """This class is the main window of the application
       It contains a notebook to which plugins can be added."""

    __gtype_name__ = "GarmonApp"
    
    ################# Properties and signals ###############
    gsignal('reset')
    
    gproperty('prefs', object, flags=gobject.PARAM_READABLE)
        
    def prop_get_prefs(self):
        return self._prefs


    def __init__(self, parent=None):
        PropertyObject.__init__(self)
        
        #Create the toplevel window
        gtk.Window.__init__(self)
        
        self._prefs = PreferenceManager('/apps/garmon')
        self._pref_cbs = []

        self._prefs.register_preference('mil.on-color', str, '#F7D30D')
        self._prefs.register_preference('mil.off-color', str, '#AAAAAA')
        self._prefs.register_preference('port', str, '/dev/ttyUSB0')
        self._prefs.register_preference('metric', bool, True)
        self._prefs.register_preference('imperial', bool, False)
        self._prefs.register_preference('plugins.save', bool, True)
        self._prefs.register_preference('plugins.start', bool, True)
        self._prefs.register_preference('plugins.saved', str, '')
        
        fname = os.path.join(GLADE_DIR, 'prefs.glade')
        xml = gtk.glade.XML(fname, 'new_prefs_vbox', 'garmon')
        self._prefs.add_dialog_page(xml, 'new_prefs_vbox', 'General')
        
        
        self._backdoor = None
        
        try:
            self.set_screen(parent.get_screen())
        except AttributeError:
            self.connect('destroy', lambda *w: gtk.main_quit())
        
        self.set_title("Garmon")
        self.set_default_size(800, 600)
        
        self.ui = gtk.UIManager()
        self.ui.insert_action_group(self._create_action_group(), 0)
        self.add_accel_group(self.ui.get_accel_group())
        
        try:
            mergeid = self.ui.add_ui_from_string(ui_info)
        except gobject.GError, msg:
            print "building menus failed: %s" % msg
        menubar = self.ui.get_widget("/MenuBar")
        menubar.show()
        
        self.main_vbox = gtk.VBox(4)
        self.main_vbox.set_homogeneous(False)
        self.add(self.main_vbox)
        
        self.main_vbox.pack_start(menubar, False, False)
        
        toolbar = self.ui.get_widget("/ToolBar")
        toolbar.set_tooltips(True)
        toolbar.show()
        
        self.main_vbox.pack_start(toolbar, False, False)
       
        # Create the notebook
        self.notebook = gtk.Notebook()
        self.notebook.set_border_width(5)
        
        self.main_vbox.pack_start(self.notebook)
        
        self.obd = OBDDevice()
        
        self.scheduler = Scheduler(self.obd)
        self.scheduler.connect('notify::working', self._scheduler_notify_working_cb)
        
        self._plugman = plugin_manager.PluginManager(self)
        if self._prefs.get_preference('plugins.start'):
            self._plugman.activate_saved_plugins()
        
        cb_id = self._prefs.preference_notify_add('port', self._notify_port_cb)
        self._pref_cbs.append(cb_id)
        
        self.show_all()

    def _create_action_group(self):
        # GtkActionEntry
        entries = (
            ( "FileMenu", None, "_File" ),          # name, stock id, label
            ( "EditMenu", None, "_Edit" ),
            ( "ViewMenu", None, "_View" ),
            ( "MonitorMenu", None, "_Monitor" ),
            ( "DeviceMenu", None, "_Device" ),
            ( "HelpMenu", None, "_Help" ),
            ( "Quit", gtk.STOCK_QUIT,
                "_Quit", "<control>Q",                      
                "Quit", self._activate_quit ),
            ( "About", gtk.STOCK_ABOUT,                   
                "_About", "<control>A",                     
                "About", self._activate_about ),
            ( "Preferences", gtk.STOCK_PREFERENCES,       
                "_Preferences", "<control>P",
                "Preferences", self._activate_prefs_dialog ),
            ( "Plugins", None,       
                "P_lugins", "<control>L",               
                "Plugin Manager", self._activate_plugin_dialog ),
            ( "Reset", gtk.STOCK_REFRESH,
                "_Reset", "<control>R",
                "Reset Device", self._activate_reset )
            );
        
        # GtkToggleActionEntry
        toggle_entries = (
            ( "Monitor", gtk.STOCK_EXECUTE,
                "_Monitor", "<control>M",
                "Monitoring", self._activate_monitor,
                False ),
            ( "FullScreen", gtk.STOCK_FULLSCREEN,
                "_Full Screen", "F11",
                "Full Screen", self._toggle_fullscreen,
                False ),
            ( "PythonShell", None,
                "_Python Shell", "",
                "Show/Hide Python Shell", self._toggle_python_shell,
                False ),
            );


        # Create the menubar and toolbar
        action_group = gtk.ActionGroup("MainWindowActions")
        action_group.add_actions(entries)
        action_group.add_toggle_actions(toggle_entries)

        return action_group

    
    def _notify_port_cb(self, pname, pvalue, ptype, args):
        self.obd.portname = pvalue

    def _activate_prefs_dialog(self, action):
        self.prefs.show_dialog()
        

    def _activate_plugin_dialog(self, action):
        self._plugman.run()
        self._plugman.hide()
        

    def _activate_about(self, action):

        dialog = gtk.AboutDialog()
        dialog.set_name("Garmon")
        dialog.set_copyright("Copyright \302\251 2007 Ben Van Mechelen")
        dialog.set_website("http://www.benvm.be")
        dialog.set_version("0.1")
        dialog.set_comments("Gnome OBD Car Monitor")
        dialog.set_authors(["Ben Van Mechelen"])
        dialog.set_license(gpl)
        
        ## Close dialog on user response
        dialog.connect ("response", lambda d, r: d.destroy())
        dialog.show()
        

    def _activate_quit(self, action):

        dialog = gtk.MessageDialog(self, gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_QUESTION, gtk.BUTTONS_OK_CANCEL,
            _("Do You Really want to quit?"))
            
        dialog.show()
        res = dialog.run()
        if res == gtk.RESPONSE_OK:
            if self._prefs.get_preference('plugins.save'):
                self._plugman.save_active_plugins()
            #TODO: Clean things up
            gtk.main_quit()
        dialog.destroy()

    def _activate_monitor(self, action):
        self.scheduler.working = action.get_active()
    
    def _scheduler_notify_working_cb(self, scheduler, pspec):
        self.ui.get_widget('/ToolBar/Monitor').set_active(scheduler.working)
        self.ui.get_widget('/MenuBar/DeviceMenu/Monitor').set_active(scheduler.working)
            
            
    def _toggle_fullscreen(self, action):
        if action.get_active():
            self.fullscreen()
        else:
            self.unfullscreen()


    def _toggle_python_shell(self, action):
        if action.get_active():
            if self._backdoor:
                self._backdoor.show()
            else:
                self._backdoor = BackDoor(self)
                self.main_vbox.pack_end(self._backdoor)                
        else:
            if self._backdoor:
                self._backdoor.hide()           


    def _activate_reset(self, action):
        self.reset()

    ####################### Public Interface ###################
    
    def reset(self):
        """This methods stops all stoppable plugins, closes the obd device
           and tries to reopen it."""
        if self.obd.connected:
            for name, plugin in self._plugman.stoppable_plugins:
                plugin.stop()
            self.obd.close()

        try:
            self.obd.open(self.prefs.get_preference('port'))
        except OBDPortError, e:
            err, msg = e
            dialog = gtk.MessageDialog(self, gtk.DIALOG_DESTROY_WITH_PARENT,
                                             gtk.MESSAGE_WARNING, gtk.BUTTONS_OK,
                                             err + '\n\n' + msg + '\n\n' + 
                                             _("Please make sure the device is connected and your settings are correct"))

            dialog.run()
            dialog.destroy()
        finally:
            self.emit('reset')   

                        
        
def main():
    GarmonApp()
    gtk.main()


if __name__ == '__main__':
    global PLUGIN_DIR
    directory = os.path.dirname(__file__)
    PLUGIN_DIR = os.path.join(directory, '../plugins')
    main()

