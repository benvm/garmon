#!/usr/bin/python
#
# garmon.py
#
# Copyright (C) Ben Van Mechelen 2007-2011 <me@benvm.be>

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
from gobject import GObject
import gtk
import locale
import gettext
import os

# set up gettext for translations
locale.setlocale(locale.LC_ALL, '')
from gettext import gettext as _
gettext.textdomain('garmon')

import garmon
from garmon import UI_DIR, GARMON_VERSION, PIXMAP_DIR, logger

import garmon.plugin_manager as plugin_manager

from garmon.prefs import PreferenceManager
from garmon.obd_device import ELMDevice, OBDError, OBDDataError, OBDPortError
from garmon.command_queue import CommandQueue, QueueTimer
from garmon.property_object import PropertyObject, gproperty, gsignal
from garmon.backdoor import BackDoor

GTK_RECOMMENDED = (2,16,0)
GTK_VERSION = gtk.ver
if GTK_VERSION < GTK_RECOMMENDED:
    logger.warning('Recommended version of pygtk is %s, but found %s' % (GTK_RECOMMENDED, GTK_VERSION))
    logger.warning('Expect warning messages from UI Builder')

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



class GarmonApp(gobject.GObject, PropertyObject):
    """This class is the main class of the application."""

    __gtype_name__ = "GarmonApp"
    
    ################# Properties and signals ###############
    gsignal('reset')
    
    def __init__(self):
        gobject.GObject.__init__(self)
        PropertyObject.__init__(self)
        
        #Create the toplevel window
        self.window = gtk.Window()
        
        icon = gtk.gdk.pixbuf_new_from_file(os.path.join(PIXMAP_DIR, 
                                                         'garmon.svg'))
        gtk.window_set_default_icon_list(icon)
        
        self.builder = gtk.Builder()
        self.builder.set_translation_domain('garmon')
        self._setup_prefs()
        
        self._backdoor = None
        
        self.window.connect('delete-event', self._window_delete_event_cb)
        
        self.window.set_title("Garmon")
        self.window.set_default_size(880, 900)
        
        self.ui = gtk.UIManager()
        self.ui.insert_action_group(self._create_action_group(), 0)
        self.window.add_accel_group(self.ui.get_accel_group())
        
        try:
            mergeid = self.ui.add_ui_from_string(ui_info)
        except gobject.GError, msg:
            logger.error("building menus failed: %s" % msg)
        menubar = self.ui.get_widget("/MenuBar")
        menubar.show()
        
        self.main_vbox = gtk.VBox(4)
        self.main_vbox.set_homogeneous(False)
        self.window.add(self.main_vbox)
        
        self.main_vbox.pack_start(menubar, False, False)
        
        toolbar = self.ui.get_widget("/ToolBar")
        toolbar.set_tooltips(True)
        toolbar.show()
        
        self.main_vbox.pack_start(toolbar, False, False)
       
        # Create the notebook
        self.notebook = gtk.Notebook()
        self.notebook.set_border_width(5)
        
        self.main_vbox.pack_start(self.notebook)
        
        self.device = ELMDevice(self)
        
        self.queue = CommandQueue(self.device)
        self.queue.connect('state_changed', self._queue_state_changed_cb)
        
        self._statusbar = gtk.Statusbar()    
        self.main_vbox.pack_end(self._statusbar, False, False)    
        timer = QueueTimer(self.queue)
        self._statusbar.pack_start(timer)
        
        self._plugman = plugin_manager.PluginManager(self)
        if self.prefs.get('plugins.start'):
            self._plugman.activate_saved_plugins()
        
        
        self.window.show_all()


    def _setup_prefs(self):
    
        baudrates = (9600, 38400, 57600, 115200)
        higher_rates = (57600, 115200)
    
        self.prefs = PreferenceManager(self)
        self._pref_cbs = []

        self.prefs.register('mil.on-color', '#F7D30D')
        self.prefs.register('mil.off-color', '#AAAAAA')
        self.prefs.register('metric', True)
        self.prefs.register('imperial', False)
        self.prefs.register('plugins.save', True)
        self.prefs.register('plugins.start', True)
        self.prefs.register('plugins.saved', 'Live Data,DTC Reader,DTC Clearer')
        
        fname = os.path.join(UI_DIR, 'general_prefs.ui')
        self.builder.add_from_file(fname)
        
        self.prefs.add_dialog_page('general_prefs_vbox', _('General'))
        
               

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
        dialog.set_copyright("Copyright \302\251 2007-2011 Ben Van Mechelen")
        dialog.set_website("http://garmon.sourceforge.net")
        dialog.set_version(GARMON_VERSION)
        dialog.set_comments(_("Gtk OBD Car Monitor"))
        dialog.set_authors(["Ben Van Mechelen <me@benvm.be>"])
        dialog.set_license(gpl)
        dialog.set_translator_credits(_("translator-credits"))
        
        ## Close dialog on user response
        dialog.connect ("response", lambda d, r: d.destroy())
        dialog.show()
        

    def _activate_quit(self, action=None):

        dialog = gtk.MessageDialog(self.window, gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_QUESTION, gtk.BUTTONS_OK_CANCEL,
            _("Do You Really want to quit?"))
            
        dialog.show()
        res = dialog.run()
        if res == gtk.RESPONSE_OK:
            if self.prefs.get('plugins.save'):
                self._plugman.save_active_plugins()
            #TODO: Clean things up
            self.prefs.save()
            gtk.main_quit()
        dialog.destroy()

    def _activate_monitor(self, action):
        if action.get_active(): 
            if not self.queue.working:
                self.queue.start()
        elif self.queue.working :
            self.queue.stop()
    
    def _queue_state_changed_cb(self, queue, working):
        self.ui.get_widget('/ToolBar/Monitor').set_active(working)
        self.ui.get_widget('/MenuBar/DeviceMenu/Monitor').set_active(working)

    def _window_delete_event_cb(self, window, event):
        self._activate_quit()
        return True
            
            
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
            self.device.open()
        except OBDPortError, e:
            err, msg = e
            dialog = gtk.MessageDialog(self.window, gtk.DIALOG_DESTROY_WITH_PARENT,
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

