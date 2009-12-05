#!/usr/bin/python
#
# dashboard.py
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


# A lot of the cairo ideas and graphics for the default theme come 
# from Maclow's Cairo Clock. http://macslow.thepimp.net/cairo-clock


import os
import math
from gettext import gettext as _

import gobject
import gtk
from gtk import gdk

import pango
import cairo
from cairo import OPERATOR_SOURCE, OPERATOR_OVER, CONTENT_COLOR_ALPHA
import rsvg

import garmon
import garmon.plugin
from garmon import logger
from garmon.plugin import Plugin, STATUS_STOP, STATUS_WORKING, STATUS_PAUSE
from garmon.obd_device import OBDDataError, OBDPortError
from garmon.sensor import StateMixin, UnitMixin, Sensor
from garmon.property_object import PropertyObject, gproperty, gsignal


__name = _('DashboardCairo')
__version = '0.3'
__author = 'Ben Van Mechelen'
__description = _('A dashboard-like plugin with meters showing OBD information')
__class = 'DashBoard'



THEME_FILENAMES = {
    'backplate':            'backplate.svg',
    'backplate-shadow':     'backplate-shadow.svg',
    'glass':                'glass.svg',
    'needle':               'needle.svg',
    'rim':                  'rim.svg',
}


class Theme (object):
    def __init__(self, name, path):
        self.name = name
        self.path = path
        self.width = None
        self.height = None	  
        self.backplate = None
        self.backplate_shadow = None
        self.glass = None
        self.centric_needle = None
        self.excentric_needle = None
        self.rim = None	
        self.background = None


class DashBoard (gtk.VBox, Plugin):
    __gtype_name__='DashBoardCairo'
    
    gproperty('theme', object) 
    
    def prop_get_theme (self):
        return self._theme
        
        
    def __init__(self, app) :
        gtk.VBox.__init__(self)
        Plugin.__init__(self)
        
        self.app = app
        self.dir = os.path.dirname(__file__)
        self._pref_cbs = []
        self._app_cbs = []
        self._notebook_cbs = []
        self._scheduler_cbs = []
        self._obd_cbs = []
        self._theme = None
                
        app.prefs.register('dashboard.background', '#2F2323')
        app.prefs.register('dashboard.theme', 'default')

        fname = os.path.join(self.dir, 'dashboard.ui')
        builder = gtk.Builder()
        builder.set_translation_domain('garmon')
        builder.add_from_file(fname)
        app.prefs.add_dialog_page(builder, 'prefs-vbox', _('Dashboard'))
        
        self._background = gtk.gdk.color_parse(app.prefs.get('dashboard.background'))

        cb_id = app.prefs.add_watch('dashboard.background', 
                                                self._prefs_notify_color_cb)
        self._pref_cbs.append(('dashboard.background', cb_id))
        cb_id = app.prefs.add_watch('dashboard.theme', 
                                                self._prefs_notify_theme_cb)
        self._pref_cbs.append(('dashboard.theme', cb_id))


        if app.prefs.get('imperial'):
            self._unit_standard = 'Imperial'
        else:
            self._unit_standard = 'Metric'
            
        cb_id = app.prefs.add_watch('imperial', 
                                    self._notify_units_cb)
        self._pref_cbs.append(('imperial', cb_id))

        self.status = STATUS_STOP
        
        app.prefs.notify('dashboard.theme')
        
        self._setup_gui()
        self._setup_gauges()
        self._set_gauges_background()
        
        self._obd_cbs.append(app.device.connect('connected', self._obd_connected_cb))
        self._notebook_cbs.append(app.notebook.connect('switch-page', 
                                                self._notebook_page_change_cb))

        self._scheduler_cbs.append(self.app.scheduler.connect('notify::working', 
                                             self._scheduler_notify_working_cb))

        self._obd_connected_cb(app.device)

    def _prefs_notify_color_cb (self, pname, pvalue, args):
        logger.debug('in _prefs_notify_color_cb')
        if pname == 'dashboard.background':
            self._background = gtk.gdk.color_parse(pvalue)
            self.layout.modify_bg(gtk.STATE_NORMAL, self._background)
            self._set_gauges_background()
    
    
    def _prefs_notify_theme_cb (self, pname, pvalue, args):
        logger.debug('in _prefs_notify_theme_cb')
        if pname == 'dashboard.theme':
            theme_path = os.path.join(self.dir, 'themes', pvalue)
            logger.debug('trying to load theme: "%s" from "%s"' % (pvalue, theme_path))
            if not os.path.isdir(theme_path):
                #theme does not exist
                logger.warning('theme does not exist')
                if pvalue == 'default':
                    #and there is no default theme
                    logger.error('default theme does not exist either')
                    return
                else:
                    logger.warning('will try default')
                    self.app.prefs.set('dashboard.theme', 'default')
            else:
                t = Theme(pvalue, theme_path)
                self._change_theme(t)
            
            
    def _change_theme (self, theme):
        try:
            theme.backplate = rsvg.Handle(file=os.path.join(theme.path,'backplate.svg'))
            theme.backplate_shadow = rsvg.Handle(file=os.path.join(theme.path,'backplate-shadow.svg'))
            theme.glass = rsvg.Handle(file=os.path.join(theme.path,'glass.svg'))
            theme.centric_needle = rsvg.Handle(file=os.path.join(theme.path,'centric-needle.svg'))
            theme.excentric_needle = rsvg.Handle(file=os.path.join(theme.path,'excentric-needle.svg'))
            theme.rim = rsvg.Handle(file=os.path.join(theme.path,'rim.svg'))
            theme.width = theme.backplate_shadow.props.width
            theme.height = theme.backplate_shadow.props.height
            theme.background = self._background
        except RuntimeError, e:
            logger.error('Unable to activate the theme: %s' % e)
            return
        self._theme = theme
        self.notify('theme')


    def _setup_gui (self) :
        alignment = gtk.Alignment(0.5, 0.5, 1.0, 1.0)
        self.layout = gtk.Layout()
        alignment.add(self.layout)
        self.pack_start(alignment, True, True)
        self.layout.modify_bg(gtk.STATE_NORMAL, self._background)
        self.show_all()
        
        
    def _setup_gauges (self):
    
        self.gauges = []
        
        for item in GAUGES:
            pid = item[PID]
            index = item[INDEX]
            width, height = item[SIZE]
            
            gauge = item[TYPE](pid, index, self._theme, width, height)
                
            if item[VALUES]:
                min_value, max_value, idle_value = item[VALUES]
                gauge.set_properties(min_value=min_value, 
                                     max_value=max_value, 
                                     idle_value=idle_value)
            if item[ANGLES]:
                min_angle, max_angle = item[ANGLES]
                gauge.set_properties(min_angle=min_angle, 
                                     max_angle=max_angle)     
                                                          
            x, y = item[POSITION]
            self.layout.put(gauge, x, y)
            gauge.show_all()
            
            gauge.unit_standard = self._unit_standard
            
            gauge.connect('active-changed', self._gauge_active_changed_cb)
            
            gauge.idle()
            self.gauges.append(gauge)
                         
    
    def _set_gauges_background(self):
        logger.debug('in _set_gauges_background')
        for item in self.layout.get_children():
            item.modify_bg(gtk.STATE_NORMAL, self._background)
       
      
    def _obd_connected_cb(self, obd, connected=False):
        page = self.app.notebook.get_current_page()
        visible = self.app.notebook.get_nth_page(page) is self
        if visible:
            self.stop()
        self._update_supported_gauges()
        if visible:
            self.start()


    def _scheduler_notify_working_cb(self, scheduler, pspec):
        if not scheduler.working:
            for gauge in self.gauges:
                gauge.idle()
    
        
    def _notify_units_cb(self, pname, pvalue, ptype, args):
        if pname == 'imperial' and pvalue:
            self._unit_standard = 'Imperial'
        else:
            self._unit_standard = 'Metric'
        for gauge in self.gauges:
            gauge.unit_standard = self._unit_standard
       
        
    def _notebook_page_change_cb (self, notebook, no_use, page):
        plugin = notebook.get_nth_page(page)
        if plugin is self:
            self.start()
        else:
            self.stop()


    def _gauge_active_changed_cb(self, gauge, active):
        if active:
            if self.status == STATUS_WORKING:
                self.app.scheduler.add(gauge.sensor)
        else:
            self.app.scheduler.remove(gauge.sensor)
            
        
    def _update_supported_gauges (self):
        
        for gauge in self.gauges:
            if gauge.sensor.command in self.app.device.supported_pids:
                gauge.supported = True
                gauge.active = True
            else:
                gauge.supported = False

                             
    def start(self):
        if not self.status == STATUS_WORKING:
            for gauge in self.gauges:
                if gauge.active:
                    self.app.scheduler.add(gauge.sensor, False)
            self.status = STATUS_WORKING
        
        
    def stop (self):
        if not self.status == STATUS_STOP:
            for gauge in self.gauges:
                self.app.scheduler.remove(gauge.sensor)
                gauge.idle()
            self.status = STATUS_STOP
            

    def load(self):
        self.app.notebook.append_page(self, gtk.Label(_('Dashboard')))
           
            
    def unload(self):
        self.app.notebook.remove(self)
        for name, cb_id in self._pref_cbs:
            self.app.prefs.remove_watch(name, cb_id)
        for cb_id in self._app_cbs:
            self.app.disconnect(cb_id)
        for cb_id in self._notebook_cbs:
            self.app.notebook.disconnect(cb_id)
        for cb_id in self._scheduler_cbs:
            self.app.scheduler.disconnect(cb_id)
        for cb_id in self._obd_cbs:
            self.app.device.disconnect(cb_id)
        



class Gauge (gtk.EventBox, StateMixin, UnitMixin,
                              PropertyObject):
    __gtype_name__="GaugeCairo"
         
    def prop_get_value (self):
        return self._value
    
    # FIXME: min-angle and max-angle should be float, 
    # but set_property does not accept negative values for gdouble or gint.
    # Warning: value "-50" of type `gint' is invalid or out of range for property `min-angle' of type `gint'
    gproperty('min-angle', object) 
    gproperty('max-angle', object)
    gproperty('min-value', float)
    gproperty('max-value', float)
    gproperty('idle-value', float)
    gproperty('value', float, flags=gobject.PARAM_READABLE)
    
    
    def __init__ (self, pid, index, theme, width=200, height=200):
        gtk.EventBox.__init__(self)
        PropertyObject.__init__(self, command=pid, index=index)
        
        logger.info('Loading Gauge for pid: %s' %pid)
        
        self.sensor = Sensor(pid, index)
         
        self.set_size_request(width, height)   
        
        self._width = width
        self._height = height
                
        self._theme = theme
        self._set_default_values()
        
        self._value = self.idle_value
        self._draw_area = gtk.DrawingArea()
        self.add(self._draw_area)

        self.connect('button-press-event', self._button_press_cb)
        self._draw_area.connect("expose_event", self._expose_event)
        self._draw_area.connect("configure_event", self._configure_event)

    
    def __post_init__(self):
        self.connect('notify::supported', self._notify_supported_cb)
        self.connect('notify::active', self._notify_active_cb)
        self.sensor.connect('data-changed', self._sensor_data_changed_cb)
               
                
    def _notify_must_redraw(self, o, pspec):
        self._draw()
        

    def _notify_supported_cb(self, o, pspec):
        self.set_sensitive(self.supported)
        if not self.supported:
            self.active = False


    def _notify_active_cb(self, o, pspec):
        logger.debug('in _notify_active_cb')
        self._draw_area.set_sensitive(self.active)
        if self.active:
            self._draw()
        self.emit('active-changed', self.active)

    
    def _button_press_cb(self, widget, event):
        if event.type == gdk.BUTTON_PRESS:
            self.active = not self.active


    def _sensor_data_changed_cb(self, sensor, data):
        self._value = eval(self.sensor.metric_value)
        self._draw()
           
               
    def _set_default_values(self):
        raise NotImplementedError, 'Use one of the subclasses please'
        
        
    def _draw (self) :
        logger.debug('in _draw: %s' % self.sensor.command)
        
        self._main_context.set_operator(OPERATOR_SOURCE)
        self._main_context.set_source_surface(self._underlay_surface, 0.0, 0.0)
        self._main_context.paint()
        
        self._main_context.set_operator(OPERATOR_OVER)

        if self.active:
            self._draw_needle()
        
        self._main_context.set_source_surface(self._overlay_surface, 0.0, 0.0)
        self._main_context.paint()
               
        
    def _expose_event (self, widget, event):
        logger.debug('in expose event: %s' % self.sensor.command)
        
        x , y, width, height = event.area
        #FIXME: need size of widget, not of event.area???
        
        self._main_context = self._draw_area.window.cairo_create()
        self._main_context.set_operator(OPERATOR_SOURCE)
        if self._surfaces_need_update:
            self._update_surfaces()

        self._draw()

        return False


    def _configure_event (self, widget, event):
        logger.debug('in _configure_event: %s' % self.sensor.command)
        self._surfaces_need_update = True
        self.idle()


    def _update_surfaces(self):
        logger.debug('in _update_surfaces: %s' % self.sensor.command)
        
        for item in ('over', 'under'):
            target = self._main_context.get_target()
            surface = target.create_similar(CONTENT_COLOR_ALPHA, 
                                            self._width, 
                                            self._height)

            context = cairo.Context(surface)
            context.scale(1.0 * self._width / self._theme.width, 
                          1.0 * self._height / self._theme.height)
                          
            if item is 'over':
                context.set_source_rgba(self._theme.background.red_float,
                                        self._theme.background.green_float,
                                        self._theme.background.blue_float,
                                        0.0)
            else: 
                context.set_source_rgba(self._theme.background.red_float,
                                        self._theme.background.green_float,
                                        self._theme.background.blue_float,
                                        1.0)
                                        
            context.set_operator(OPERATOR_OVER)
            context.paint()
            
            if item == 'over':
                self._theme.glass.render_cairo(context)
                self._theme.rim.render_cairo(context)
                self._overlay_surface = surface
            else:
                self._theme.backplate_shadow.render_cairo(context)
                self._theme.backplate.render_cairo(context)
                self._underlay_surface = surface
            
        self._surfaces_need_update = False


    def update_theme (self, theme):
        logger.debug('in _update_theme: %s' % self.sensor.command)
        self._theme = theme
        self._surfaces_need_update = True
        window = self._draw_area.window
        window.invalidate_rect(window.allocation, False)
        window.process_updates()
        

    def idle (self) :
        """Set value to the defined idle value""" 
        logger.debug('setting gauge idle')
        self._value = self.idle_value

        

class ExCentricGauge (Gauge) :
    __gtype_name__="ExCentricGaugeCairo"
    def _set_default_values(self):
    
        self._needle_x = self._theme.width / 2.0
        self._needle_y = self._theme.height * 4 / 5
        self._needle_scale = 1.2
        
        self.max_value = 250.0
        self.min_value = 0.0
        self.idle_value = 0.0
        self.max_angle = 300.0
        self.min_angle = 240.0
        
        
    def _draw_needle(self):
        logger.debug('in _update_theme: %s' % self.sensor.command)
        
        angle_range = self.max_angle - self.min_angle
        value_range = self.max_value - self.min_value
        value = self._value
        if value < self.min_value:
            value = self.min_value
        if value > self.max_value:
            value = self.max_value
        angle = (value - self.min_value) / value_range * angle_range + self.min_angle
    
        self._main_context.save()
        self._main_context.scale(1.0 * self._width / self._theme.width, 
                                 1.0 * self._height / self._theme.height)
        self._main_context.translate(self._needle_x, self._needle_y)
        
        self._main_context.rotate(math.radians(angle)) 
        self._theme.excentric_needle.render_cairo(self._main_context)
        
        self._main_context.restore()
        

 
class LowGauge (Gauge):
    __gtype_name__="LowGaugeCairo"
    
    def _set_default_values(self):
        pass
   

    
class CentricGauge (Gauge) :
    __gtype_name__="CentricGaugeCairo"
    def _set_default_values(self):
        
        self._needle_x = self._theme.width / 2.0
        self._needle_y =  self._theme.height / 2.0
        self._needle_scale = 1.0
        
        self.max_value = 250.0
        self.min_value = 0.0
        self.idle_value = 0.0
        self.max_angle = 50.0
        self.min_angle = 130.0
        
        
    def _draw_needle(self):
        logger.debug('in _update_theme: %s' % self.sensor.command)
        
        angle_range = self.max_angle - self.min_angle
        value_range = self.max_value - self.min_value
        value = self._value
        if value < self.min_value:
            value = self.min_value
        if value > self.max_value:
            value = self.max_value
        angle = (value - self.min_value) / value_range * angle_range + self.min_angle
    
        self._main_context.save()
        self._main_context.scale(1.0 * self._width / self._theme.width, 
                                 1.0 * self._height / self._theme.height)
        self._main_context.translate(self._needle_x, self._needle_y)
        
        self._main_context.rotate(math.radians(angle)) 
        self._theme.centric_needle.render_cairo(self._main_context)
        
        self._main_context.restore()
        
        
    
(PID, INDEX, POSITION, SIZE, METRIC, IMPERIAL, VALUES, ANGLES, TYPE) = range(9)   
    
GAUGES = [
    ('010D', 0, (0,0), (300, 300), 'speed_metric.svg', None, (0, 250, 0), None, CentricGauge),
    ('010C', 0, (450,0), (300, 300), 'rpm.svg', None, (0, 8000, 0), None, CentricGauge),
    ('0105', 0, (300,0), (150, 150), 'temp_metric.svg', None, (60, 120, 60), None, ExCentricGauge),
    ('0104', 0, (300,150), (150, 150), 'load.svg', None, (0, 100, 0), None, CentricGauge),
    
]
