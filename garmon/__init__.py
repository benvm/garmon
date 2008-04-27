import os
import sys


DIRECTORY = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
INSTALLED = not os.path.exists(os.path.join(DIRECTORY,"ChangeLog"))

if INSTALLED:
    from defs import *
    if not PYTHON_DIR in sys.path:
        sys.path.insert(0, PYTHONDIR)
else:
    VERSION =                   "0.1"
    PLUGIN_DIR =                os.path.join(DIRECTORY, "plugins")
    GLADE_DIR =                 os.path.join(DIRECTORY, "data")

def debug(msg):
    print 'Garmon DebugInfo:  * ' + msg
