version = '0.4'
author = 'Ben Van Mechelen <me@benvm.be>'
license = 'GPL v2'
copyright = ''

import os

class dirs:
    ROOT = os.path.abspath(os.path.dirname(__file__))
    UI = os.path.join(ROOT, 'data')
    PIXMAPS = os.path.join(ROOT, 'data')
    PLUGINS = os.path.join(ROOT, 'plugins')

