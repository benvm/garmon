#!/usr/bin/python
#
# garmon.py
#
# Copyright (C) Ben Van Mechelen 2007-2009 <me@benvm.be>

gpl = """
                      GNU General Public License
                
Garmon is free software.
 
You may redistribute it and/or modify it under the terms of the
GNU General Public License, as published by the Free Software
Foundation; either version 2 of the License, or (at your option)
any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, write to:
  The Free Software Foundation, Inc.,
  51 Franklin Street, Fifth Floor
  Boston, MA  02110-1301, USA.
"""

import gobject
import gtk
from gtk import glade
import locale
import gettext
import os

# set up gettext for translations
locale.setlocale(locale.LC_ALL, '')
from gettext import gettext as _
gettext.textdomain('garmon')
gtk.glade.textdomain('garmon')

import garmon
from garmon import GLADE_DIR, GARMON_VERSION, PIXMAP_DIR, logger

import garmon.plugin_manager as plugin_manager

from garmon.prefs import PreferenceManager
from garmon.obd_device import ELMDevice, OBDError, OBDDataError, OBDPortError
from garmon.scheduler import Scheduler, SchedulerTimer
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
        
        icon = gtk.gdk.pixbuf_new_from_file(os.path.join(PIXMAP_DIR, 
                                                         'garmon.svg'))
        gtk.window_set_default_icon_list(icon)

        self._setup_prefs()
        
        self._backdoor = None
        
        try:
            self.set_screen(parent.get_screen())
        except AttributeError:
            self.connect('destroy', lambda *w: gtk.main_quit())
        
        self.set_title("Garmon")
        self.set_default_size(880, 900)
        
        self.ui = gtk.UIManager()
        self.ui.insert_action_group(self._create_action_group(), 0)
        self.add_accel_group(self.ui.get_accel_group())
        
        try:
            mergeid = self.ui.add_ui_from_string(ui_info)
        except gobject.GError, msg:
            logger.error("building menus failed: %s" % msg)
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
        
        self.device = ELMDevice()
        self.device.baudrate = int(self.prefs.get('device.baudrate'))
        
        self.scheduler = Scheduler(self.device)
        self.scheduler.connect('notify::working', self._scheduler_notify_working_cb)
        
        self._statusbar = gtk.Statusbar()    
        self.main_vbox.pack_end(self._statusbar, False, False)    
        timer = SchedulerTimer(self.scheduler)
        self._statusbar.pack_start(timer)
        
        self._plugman = plugin_manager.PluginManager(self)
        if self._prefs.get('plugins.start'):
            self._plugman.activate_saved_plugins()
        
        
        self.show_all()


    def _setup_prefs(self):
    
        baudrates = (9600, 38400, 57600, 115200)
        higher_rates = (57600, 115200)
    
        self._prefs = PreferenceManager()
        self._pref_cbs = []

        self._prefs.register('mil.on-color', '#F7D30D')
        self._prefs.register('mil.off-color', '#AAAAAA')
        self._prefs.register('device.portname', '/dev/ttyUSB0')
        self._prefs.register('device.baudrate', 38400)
        self._prefs.register('device.initial-baudrate', 38400)
        self._prefs.register('device.increase-baudrate', False)
        self._prefs.register('device.higher-baudrate', 115200)
        self._prefs.register('metric', True)
        self._prefs.register('imperial', False)
        self._prefs.register('plugins.save', True)
        self._prefs.register('plugins.start', True)
        self._prefs.register('plugins.saved', '')
        
        fname = os.path.join(GLADE_DIR, 'prefs.glade')
        xml = gtk.glade.XML(fname, 'general_prefs_vbox', 'garmon')
        self._prefs.add_dialog_page(xml, 'general_prefs_vbox', _('General'))
        
        xml = gtk.glade.XML(fname, 'device_prefs_vbox', 'garmon')
        
        combo = xml.get_widget('preference;combo;int;device.baudrate')
        model = gtk.ListStore(gobject.TYPE_INT)
        for item in baudrates:
            model.append((item,))
        combo.set_model(model)

        combo = xml.get_widget('preference;combo;int;device.higher-baudrate')
        model = gtk.ListStore(gobject.TYPE_INT)
        for item in higher_rates:
            model.append((item,))
        combo.set_model(model)
        
        self._prefs.add_dialog_page(xml, 'device_prefs_vbox', _('Device'))
        cb_id = self._prefs.add_watch('device.portname', self._notify_port_cb)
        cb_id = self._prefs.add_watch('device.baudrate', self._notify_port_cb)
        
                

    def _create_action_group(self):
        # GtkActionEntry
        entries = (
            ( "FileMenu", None, _("_File") ),          # name, stock id, label
            ( "EditMenu", None, _("_Edit") ),
            ( "ViewMenu", None, _("_View") ),
            ( "MonitorMenu", None, _("_Monitor") ),
            ( "DeviceMenu", None, _("_Device") ),
            ( "HelpMenu", None, _("_Help") ),
            ( "Quit", gtk.STOCK_QUIT,
                _("_Quit"), "<control>Q",                      
                _("Quit"), self._activate_quit ),
            ( "About", gtk.STOCK_ABOUT,                   
                _("_About"), "<control>A",                     
                _("About"), self._activate_about ),
            ( "Preferences", gtk.STOCK_PREFERENCES,       
                _("_Preferences"), "<control>P",
                _("Preferences"), self._activate_prefs_dialog ),
            ( "Plugins", None,       
                _("P_lugins"), "<control>L",               
                _("Plugin Manager"), self._activate_plugin_dialog ),
            ( "Reset", gtk.STOCK_REFRESH,
                _("_Reset"), "<control>R",
                _("Reset Device"), self._activate_reset )
            );
        
        # GtkToggleActionEntry
        toggle_entries = (
            ( "Monitor", gtk.STOCK_EXECUTE,
                _("_Monitor"), "<control>M",
                _("Monitoring"), self._activate_monitor,
                False ),
            ( "FullScreen", gtk.STOCK_FULLSCREEN,
                _("_Full Screen"), "F11",
                _("Full Screen"), self._toggle_fullscreen,
                False ),
            ( "PythonShell", None,
                _("_Python Shell"), "",
                _("Show/Hide Python Shell"), self._toggle_python_shell,
                False ),
            );


        # Create the menubar and toolbar
        action_group = gtk.ActionGroup("MainWindowActions")
        action_group.add_actions(entries)
        action_group.add_toggle_actions(toggle_entries)

        return action_group

    
    def _notify_port_cb(self, pname, pvalue, args):
        if pname == 'device.portname':
            self.device.portname = pvalue
        elif pname == 'device.baudrate':
            self.device.baudrate = self.prefs.get(pname)


    def _activate_prefs_dialog(self, action):
        self.prefs.show_dialog()
        

    def _activate_plugin_dialog(self, action):
        self._plugman.run()
        self._plugman.hide()
        

    def _activate_about(self, action):

        dialog = gtk.AboutDialog()
        dialog.set_name("Garmon")
        dialog.set_copyright("Copyright \302\251 2007 Ben Van Mechelen")
        dialog.set_website("http://garmon.sourceforge.net")
        dialog.set_version(GARMON_VERSION)
        dialog.set_comments(_("Gtk OBD Car Monitor"))
        dialog.set_authors(["Ben Van Mechelen <me@benvm.be>"])
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
            if self._prefs.get('plugins.save'):
                self._plugman.save_active_plugins()
            #TODO: Clean things up
            self._prefs.save()
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
        if self.device.connected:
            for name, plugin in self._plugman.plugins:
                plugin.stop()
            self.device.close()

        try:
            self.device.open(self.prefs.get('device.portname'))
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

