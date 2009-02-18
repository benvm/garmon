#!/usr/bin/python
#
# plugin_manager.py
#
# Copyright (C) Ben Van Mechelen 2007-2009 <me@benvm.be>
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


import os
import imp
from gettext import gettext as _
import gobject
import gtk

import garmon

from garmon import logger
from garmon.plugin import Plugin
from garmon.property_object import PropertyObject, gproperty, gsignal


(
    COLUMN_ACTIVE,
    COLUMN_NAME,
    COLUMN_MODULE,
    COLUMN_PATH,
    COLUMN_VERSION,
    COLUMN_AUTHOR,
    COLUMN_DESCRIPTION,
    COLUMN_CLASS,
    COLUMN_INSTANCE
) = range(9)



class PluginManager(gtk.Dialog, PropertyObject):
    """ This class looks for available plugins from the plugin directory
        and activates them when they are selected
    """
    __gtype_name__ = "PluginManager"
 
    ################# Properties and signals ###############   
    gproperty('plugins', object, flags=gobject.PARAM_READABLE)
    
    def prop_get_plugins(self):
        return self._active_plugins
 
                              
    def __init__(self, app):
        """ @param app: GarmonApp
        """
        gtk.Dialog.__init__(self, _("Garmon Plugin Manager"),
                                  app, gtk.DIALOG_DESTROY_WITH_PARENT,
                                  (gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE,))
        PropertyObject.__init__(self)
                                  
        self.app = app

        
        self._active_plugins = []
        
        self.resize(550, 300)
        
        hbox = gtk.HBox(False, 10)
        self.vbox.pack_start(hbox)
        hbox.show()
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        hbox.pack_start(sw, False, False, 0)

        # create tree model
        self._treemodel = self._create_treemodel()

        # create tree view
        listview = gtk.TreeView(self._treemodel)
        listview.set_rules_hint(True)
        listview.set_headers_visible(False)
        listview.set_search_column(COLUMN_NAME)
        
        selection = listview.get_selection()
        selection.set_mode(gtk.SELECTION_SINGLE)

        selection.connect("changed", self._selection_changed)
        
        sw.add(listview)
        
        # add columns to the tree view
        self._add_columns(listview)
        
        self._info_box = PluginInfoBox()
        hbox.pack_start(self._info_box, False)
        
        self._load_available_plugins()


    def _create_treemodel(self):
        list_store = gtk.ListStore(gobject.TYPE_BOOLEAN,
                                    gobject.TYPE_STRING,
                                    gobject.TYPE_PYOBJECT,
                                    gobject.TYPE_STRING,
                                    gobject.TYPE_STRING,
                                    gobject.TYPE_STRING,
                                    gobject.TYPE_STRING,
                                    gobject.TYPE_STRING,
                                    gobject.TYPE_PYOBJECT)
        return list_store
            
            
    def _add_columns(self, listview):
        model = self._treemodel
        
        renderer = gtk.CellRendererToggle()
        column = gtk.TreeViewColumn(None, renderer,
                                    active=COLUMN_ACTIVE)
        listview.append_column(column)
        renderer.connect('toggled', self._active_toggled, model)
                
        column = gtk.TreeViewColumn(None, gtk.CellRendererText(),
                                    text=COLUMN_NAME)
        listview.append_column(column) 


    def _active_toggled(self, cell, path, model):
        iter = model.get_iter((int(path),))
        active = model.get_value(iter, COLUMN_ACTIVE)
        plugin = model.get_value(iter, COLUMN_NAME)

        if active:
            self._deactivate_plugin(plugin)
            active = False
            instance = None
        else:
            instance = self._activate_plugin(iter)
            if instance:
                active = True
        
        model.set(iter, COLUMN_ACTIVE, active,
                        COLUMN_INSTANCE, instance)



    def _selection_changed(self, selection):
        treeview = selection.get_tree_view()
        model, iter = selection.get_selected()
        
        if iter:
            name, path, version, author, \
            description = model.get(iter, COLUMN_NAME,
                                          COLUMN_PATH,
                                          COLUMN_VERSION,
                                          COLUMN_AUTHOR,
                                          COLUMN_DESCRIPTION)

        self._info_box.set(name, version, author, description)


    def _load_plugin(self, plugin, path):
        try:
            module_info = imp.find_module(plugin, [path])
            module = imp.load_module(plugin, *module_info)
            
            iter = self._treemodel.append()
            self._treemodel.set(iter,
                                COLUMN_ACTIVE, False,
                                COLUMN_NAME, getattr(module,'__name'),
                                COLUMN_MODULE, module,
                                COLUMN_PATH, module_info[1],
                                COLUMN_VERSION, getattr(module,'__version'),
                                COLUMN_AUTHOR, getattr(module,'__author'),
                                COLUMN_DESCRIPTION, getattr(module,'__description'),
                                COLUMN_CLASS, getattr(module,'__class'))
                                            
        except ImportError, e:
            logger.error(_('failed to load plugin: ') + plugin)
            logger.error(e)
        finally:
            if module_info[0]:
                module_info[0].close()


    def _activate_plugin(self, iter):
        plugin = self._treemodel.get_value(iter, COLUMN_NAME)
        cls = self._treemodel.get_value(iter, COLUMN_CLASS)
        module = self._treemodel.get_value(iter, COLUMN_MODULE)
        instance = None
        try:
            attr = getattr(module, cls)
            instance = attr(self.app)
        except:
            logger.error(_('Failed to activate plugin %s') % plugin)
            if instance:
                instance = None
            raise
            return None
        
        if isinstance(instance, Plugin):
            self._active_plugins.append((plugin, instance))
        else:
            logger.error(_('%s does not seem to be a valid Plugin') % instance)
            instance = None
            return None

        try:
            if instance.ui_info:
                instance.merge_id = self.app.ui.add_ui_from_string(instance.ui_info)
                self.app.ui.insert_action_group(instance.action_group, 0)
        except gobject.GError, msg:
                logger.error(_("building menus failed: %s") % msg)
        
        if hasattr(instance, 'load'):                    
            instance.load()

        logger.info(_('Plugin activated: %s') % plugin)
        logger.debug(instance)
        return instance
            
            
    def _deactivate_plugin(self, plugin):
        
        instance = self._plugin_instance_from_string(plugin)
        istr = str(instance)
        
        if instance.action_group:
            self.app.ui.remove_action_group(instance.action_group)
        if instance.merge_id:
            self.app.ui.remove_ui(instance.merge_id)
        if hasattr(instance, 'unload'):
            instance.unload()
        del instance
            
        for item in self._active_plugins:
            string, i = item
            if string ==  plugin:
                self._active_plugins.remove(item)
                    
        logger.info(_('Plugin deactivated: %s') % plugin)
        logger.debug(_('Plugin deactivated: %s') % istr)
        
        
    def _activate_saved_plugins_cb(self, model, path, iter, plugins):
        plugin = model.get_value(iter, COLUMN_NAME)
        if plugin in plugins:
            if self._activate_plugin(iter):
                model.set_value(iter, COLUMN_ACTIVE, True)
        
        
    def _load_available_plugins(self):
        
        for dname in os.listdir(garmon.PLUGIN_DIR):
            path = os.path.join(garmon.PLUGIN_DIR, dname)
            fname = dname + '.py'
            if os.path.isdir(path):
                if os.path.exists(os.path.join(path, fname)):
                    self._load_plugin(dname, path)
                else:
                    logger.warning(_('No file %s was found in %s') % (fname, path))
             

    def _plugin_instance_from_string(self, string):
        for ret_str, instance in self._active_plugins:
            if string == ret_str:
                return instance
        return None
        
    ####################### Public Interface ###################        
        
    def save_active_plugins(self):
        string = ''
        for name, plugin in self._active_plugins:
            string += name + ','
        self.app.prefs.set_preference('plugins.saved', string)
                    

    def activate_saved_plugins(self):
        string = self.app.prefs.get_preference('plugins.saved')
        plugins = string.split(',')
        if plugins:
            self._treemodel.foreach(self._activate_saved_plugins_cb, plugins)        
        
               
    def run(self):
        self.show_all()
        gtk.Dialog.run(self)
        
        
def _strip_extension(string):
    if string.rfind('.') > -1:
        return string[:string.rfind('.')], string[string.rfind('.')+1:]
    return string, ''        
        
        
        
class PluginInfoBox(gtk.VBox):

    def __init__(self):
        gtk.VBox.__init__(self, False, 10)
        
        #Name
        name_hbox = gtk.HBox()
        self.pack_start(name_hbox, False)
        self.name_label = gtk.Label('')
        self.name_label.set_use_markup(True)
        name_hbox.pack_start(self.name_label, False)
        
        vbox = gtk.VBox(False, 7)
        self.pack_start(vbox, False)
        
        #Version
        version_vbox = gtk.VBox(False, 3)
        vbox.pack_start(version_vbox, False)
        hbox = gtk.HBox()
        version_vbox.pack_start(hbox)
        version_label = gtk.Label(_('<b>Version: </b>'))
        version_label.set_use_markup(True)
        hbox.pack_start(version_label, False)
        hbox = gtk.HBox()
        version_vbox.pack_start(hbox)
        self.version_text = gtk.Label('')
        hbox.pack_start(self.version_text, False)
        
        #Author
        author_vbox = gtk.VBox(False, 3)
        vbox.pack_start(author_vbox, False)
        hbox = gtk.HBox()
        author_vbox.pack_start(hbox)
        author_label = gtk.Label(_('<b>Author: </b>'))
        author_label.set_use_markup(True)
        hbox.pack_start(author_label, False)
        hbox = gtk.HBox()
        author_vbox.pack_start(hbox)
        self.author_text = gtk.Label('')
        hbox.pack_start(self.author_text, False)
        
        #Description
        descr_vbox = gtk.VBox(False, 3)
        vbox.pack_start(descr_vbox, False)
        hbox = gtk.HBox()
        descr_vbox.pack_start(hbox)
        descr_label = gtk.Label(_('<b>Description: </b>'))
        descr_label.set_use_markup(True)
        hbox.pack_start(descr_label, False)
        hbox = gtk.HBox()
        descr_vbox.pack_start(hbox)
        self.descr_text = gtk.Label('')
        hbox.pack_start(self.descr_text, False)
        

        self.show_all()
        

    def set(self, name, version, author, description):

        self.name_label.set_markup('<span size=\"x-large\">%s</span>' % name)
        self.version_text.set_text(version)
        self.author_text.set_text(author)
        self.descr_text.set_text(description)

        
if __name__ == '__main__':
    pass
