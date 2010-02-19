#!/usr/bin/python
# -*- coding: iso-8859-15 -*-
#
# logger.py
#
# Copyright (C) Ben Van Mechelen 2010 <me@benvm.be>
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

import logging

LEVELS = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')

logging.basicConfig(level=logging.INFO,
                    format='%(name)-10s: %(levelname)-10s %(message)s')

log = logging.getLogger('Garmon')

def set_level (level):
    log.setLevel(getattr(logging, level))
 
