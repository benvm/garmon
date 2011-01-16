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


import os
import math
from gettext import gettext as _

import gobject
import gtk
from gtk import gdk

import garmon
import garmon.plugin

from garmon.plugin import Plugin, STATUS_STOP, STATUS_WORKING, STATUS_PAUSE
from garmon.obd_device import OBDDataError, OBDPortError
from garmon.sensor import StateMixin, UnitMixin, Sensor
from garmon.property_object import PropertyObject, gproperty, gsignal


__name = _('Dashboard')
__version = garmon.GARMON_VERSION
__author = 'Ben Van Mechelen'
__description = _('A dashboard-like plugin with meters showing OBD information')
__class = 'DashBoard'



class DashBoard (gtk.VBox, Plugin):
    __gtype_name__='DashBoard'
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
                
        app.prefs.register('dashboard.needle-color', '#F20D1B')
        app.prefs.register('dashboard.background', '#2F2323')

        fname = os.path.join(self.dir, 'dashboard.ui')
        builder = gtk.Builder()
        builder.set_translation_domain('garmon')
        builder.add_from_file(fname)
        app.prefs.add_dialog_page(builder, 'prefs-vbox', _('Dashboard'))
        
        self._needle_color = app.prefs.get('dashboard.needle-color')
        self._background = app.prefs.get('dashboard.background')
        cb_id = app.prefs.add_watch('dashboard.needle-color', 
                                                self._prefs_notify_color_cb)
        self._pref_cbs.append(('dashboard.needle-color', cb_id))
        cb_id = app.prefs.add_watch('dashboard.background', 
                                                self._prefs_notify_color_cb)
        self._pref_cbs.append(('dashboard.background', cb_id))

        if app.prefs.get('imperial'):
            self._unit_standard = 'Imperial'
        else:
            self._unit_standard = 'Metric'
            
        cb_id = app.prefs.add_watch('imperial', 
                                    self._notify_units_cb)
        self._pref_cbs.append(('imperial', cb_id))

        self.status = STATUS_STOP
        
        self._setup_gui()
        self._setup_gauges()
        self._set_gauges_background()
        
        self._obd_cbs.append(app.device.connect('connected', self._obd_connected_cb))
        self._notebook_cbs.append(app.notebook.connect('switch-page', 
                                                self._notebook_page_change_cb))

        self._scheduler_cbs.append(self.app.scheduler.connect('notify::working', 
                                             self._scheduler_notify_working_cb))        

        self._obd_connected_cb(app.device)

    def _prefs_notify_color_cb(self, pname, pvalue, args):
        if pname == 'dashboard.needle-color':
            self._needle_color = pvalue
            for gauge in self.gauges:
                gauge.needle_color = self._needle_color
        elif pname == 'dashboard.background':
            self._background = pvalue
            self.layout.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(self._background))
            self._set_gauges_background()
       
        
    def _setup_gui (self) :
        alignment = gtk.Alignment(0.5, 0.5, 1.0, 1.0)
        self.layout = gtk.Layout()
        alignment.add(self.layout)
        self.pack_start(alignment, True, True)
        self.layout.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(self._background))
        self.show_all()
        
        
    def _setup_gauges (self):
    
        self.gauges = []
        
        for item in GAUGES:
            pid = item[PID]
            index = item[INDEX]
            
            metric = gtk.gdk.pixbuf_new_from_file(os.path.join(self.dir, item[METRIC]))
            if item[IMPERIAL]:
                imperial = gtk.gdk.pixbuf_new_from_file(os.path.join(self.dir, item[IMPERIAL]))
            else:
                imperial = None
                
            gauge = item[TYPE](pid, metric, imperial, index)
                
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
            gauge.needle_color = self._needle_color
            
            gauge.connect('active-changed', self._gauge_active_changed_cb)
            
            gauge.idle()
            self.gauges.append(gauge)
                         
    
    def _set_gauges_background(self):
        color = gtk.gdk.color_parse(self._background)
        for item in self.layout.get_children():
            item.modify_bg(gtk.STATE_NORMAL, color)
       
      
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
    __gtype_name__="Gauge"
         
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
    gproperty('needle-color', str, '#FDC62D')
    gproperty('needle-length', int)
    gproperty('needle-width', int)
    gproperty('metric-overlay', object)
    gproperty('imperial-overlay', object)
    
    
    def __init__ (self, pid, metric, imperial=None, index=0):
        if not imperial:
            imperial=metric
        gtk.EventBox.__init__(self)
        PropertyObject.__init__(self, command=pid, index=index, 
                                      metric_overlay=metric,
                                      imperial_overlay=imperial)
        self.sensor = Sensor(pid, index)
        
        width = self.metric_overlay.get_width()
        height = self.metric_overlay.get_height()    
        self.set_size_request(width, height)    
        
        self._needle_gc = None
        
        self._set_default_values()
        
        self._value = self.idle_value
        self._pixmap = None
        self._area = gtk.DrawingArea()
        self.add(self._area)

        self.connect('button-press-event', self._button_press_cb)
        self._area.connect("expose_event", self._expose_event)
        self._area.connect("configure_event", self._configure_event)

    
    def __post_init__(self):
        self.connect('notify::needle-length', self._notify_must_redraw)
        self.connect('notify::metric-overlay', self._notify_must_redraw)
        self.connect('notify::imperial-overlay', self._notify_must_redraw)
        self.connect('notify::needle-color', self._notify_needle_cb)
        self.connect('notify::needle-width', self._notify_needle_cb)
        self.connect('notify::supported', self._notify_supported_cb)
        self.connect('notify::active', self._notify_active_cb)
        self.sensor.connect('data-changed', self._sensor_data_changed_cb)
               
                
    def _notify_must_redraw(self, o, pspec):
        self._draw()
        
   
    def _notify_needle_cb(self, o, pspec):
        if pspec.name == 'needle-color':
            if self._needle_gc:
                self._needle_gc.set_rgb_fg_color(gtk.gdk.color_parse(self.needle_color))
        if pspec.name == 'needle-width':    
            self._needle_gc.line_width = width
        self._draw()


    def  _notify_supported_cb(self, o, pspec):
        self.set_sensitive(self.supported)
        if not self.supported:
            self.active = False


    def _notify_active_cb(self, o, pspec):
        self._area.set_sensitive(self.active)
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
        
        
    def _construct_needle (self) :
        angle_range = self.max_angle - self.min_angle
        value_range = self.max_value - self.min_value
        value = self._value
        if value < self.min_value:
            value = self.min_value
        if value > self.max_value:
            value = self.max_value
        angle = (value - self.min_value) / value_range * angle_range + self.min_angle
        
        point_x = int(self._needle_origin_x + self.needle_length * math.cos((angle + 180) * math.pi / 180))
        point_y = int(self._needle_origin_y + self.needle_length * math.sin((angle + 180) * math.pi / 180))
        
        side1_x = int(self._needle_origin_x + self.needle_width * math.cos((angle + 270) * math.pi / 180))
        side1_y = int(self._needle_origin_y + self.needle_width * math.sin((angle + 270) * math.pi / 180))
        
        side2_x = int(self._needle_origin_x + self.needle_width * math.cos((angle + 90) * math.pi / 180))
        side2_y = int(self._needle_origin_y + self.needle_width * math.sin((angle + 90) * math.pi / 180))
        
        return [(self._needle_origin_x, self._needle_origin_y),
                    (side1_x, side1_y),
                    (point_x, point_y),
                    (side2_x, side2_y)]
        
        
    def _draw (self) :
        if self._pixmap is None :
            return
        x, y, width, height = self.get_allocation()
        bg_gc = self.get_style().bg_gc[gtk.STATE_NORMAL]
        self._pixmap.draw_rectangle(bg_gc, True, 0, 0, width, height)
        
        if self.unit_standard == 'Imperial':
            overlay = self.imperial_overlay
        else:
            overlay = self.metric_overlay
        self._pixmap.draw_pixbuf(gtk.gdk.GC(self.window), overlay, 0, 0, 0, 0)
        
        needle = self._construct_needle()
        if self.active:
            self._pixmap.draw_polygon(self._needle_gc, True, needle)
        
        fg_gc = self.get_style().fg_gc[gtk.STATE_NORMAL]
        fg_gc.set_foreground(gtk.gdk.color_parse('#000000'))
        self._pixmap.draw_arc(fg_gc, True, 
                                     self._needle_origin_x - self._circle_radius, 
                                     self._needle_origin_y - self._circle_radius, 
                                     self._circle_radius * 2, self._circle_radius * 2, 0, 360 * 64)
                                         
        self._area.queue_draw()

        
    def _expose_event (self, widget, event):
        x , y, width, height = event.area
        widget.window.draw_drawable(widget.get_style().bg_gc[gtk.STATE_NORMAL], self._pixmap, x, y, x, y, width, height)
        return False


    def _configure_event (self, widget, event):
        x, y, width, height = widget.get_allocation()
        self._pixmap = gtk.gdk.Pixmap(widget.window, width, height)
        self._needle_gc = gtk.gdk.GC(widget.window)
        self._needle_gc.set_rgb_fg_color(gtk.gdk.color_parse(self.needle_color))
        self._needle_gc.line_width = self.needle_width
        self.idle()
        
        
    def idle (self) :
        """Set value to the defined idle value""" 
        self._value = self.idle_value
        self._draw()

        

class ExCentricGauge (Gauge) :
    __gtype_name__="ExCentricGauge"
    def _set_default_values(self):
    
        width = self.metric_overlay.get_width()
        height = self.metric_overlay.get_height()
        self._needle_origin_x = width / 2
        self._needle_origin_y = height * 4 / 5
        self.needle_length = height * 3 / 5
        self.needle_width = self.needle_length / 18
        if self.needle_width < 4: 
            self.needle_width = 4
        self._circle_radius = self.needle_width * 2
        
        self.max_value = 250.0
        self.min_value = 0.0
        self.idle_value = 0.0
        self.max_angle = 120.0
        self.min_angle = 60.0
        

 
class LowGauge (Gauge):
    __gtype_name__="LowGauge"
    
    def _set_default_values(self):
        pass
   

    
class CentricGauge (Gauge) :
    __gtype_name__="CentricGauge"
    def _set_default_values(self):
        
        width = self.metric_overlay.get_width()
        height = self.metric_overlay.get_height()
        self._needle_origin_x = width / 2
        self._needle_origin_y =  height / 2
        self.needle_length = height * 2 / 5
        self.needle_width = self.needle_length / 18
        if self.needle_width < 4: 
            self.needle_width = 4
        self._circle_radius = self.needle_width * 2
        
        self.max_value = 250.0
        self.min_value = 0.0
        self.idle_value = 0.0
        self.max_angle = 230.0
        self.min_angle = -50.0
    
(PID, INDEX, POSITION, METRIC, IMPERIAL, VALUES, ANGLES, TYPE) = range(8)   
    
GAUGES = [
    ('010D', 0, (0,0), 'speed_metric.svg', None, (0, 250, 0), None, CentricGauge),
    ('010C', 0, (400,0), 'rpm.svg', None, (0, 8000, 0), None, CentricGauge),
    ('0105', 0, (270,0), 'temp_metric.svg', None, (60, 120, 60), None, ExCentricGauge),
    ('0104', 0, (270,145), 'load.svg', None, (0, 100, 0), None, CentricGauge),
    
]
