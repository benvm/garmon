version = '0.4'
author = 'Ben Van Mechelen <me@benvm.be>'
license = 'GPL v2'
copyright = ''

import os
import locale
import gettext

class dirs:
    ROOT = os.path.abspath(os.path.dirname(__file__))
    UI = os.path.join(ROOT, 'data')
    LOCALE = os.path.join(ROOT, 'locale')
    PIXMAPS = os.path.join(ROOT, 'data')
    PLUGINS = os.path.join(ROOT, 'plugins')

# set up gettext for translations
gettext.install('garmon', dirs.LOCALE, unicode=1)
locale.bindtextdomain('garmon', dirs.LOCALE)
