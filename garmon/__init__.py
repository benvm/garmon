import os
import sys
import logging
from defs import *

DIRECTORY = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
INSTALLED = not os.path.exists(os.path.join(DIRECTORY,"ChangeLog"))


if INSTALLED:
    if not PYTHON_DIR in sys.path:
        sys.path.insert(0, PYTHONDIR)
else:
    PLUGIN_DIR =                os.path.join(DIRECTORY, "plugins")
    GLADE_DIR =                 os.path.join(DIRECTORY, "data")
    
DEBUG_LEVEL = logging.INFO
DEBUG_LEVELS = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
    
logging.basicConfig(level=DEBUG_LEVEL,
                    format='%(name)-10s: %(levelname)-10s %(message)s')

logger = logging.getLogger('Garmon')
