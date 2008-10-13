import os
import sys
from defs import *

DIRECTORY = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
INSTALLED = not os.path.exists(os.path.join(DIRECTORY,"ChangeLog"))


if INSTALLED:
    if not PYTHON_DIR in sys.path:
        sys.path.insert(0, PYTHONDIR)
else:
    PLUGIN_DIR =                os.path.join(DIRECTORY, "plugins")
    GLADE_DIR =                 os.path.join(DIRECTORY, "data")

def debug(msg):
    print 'Garmon DebugInfo:  * ' + msg
