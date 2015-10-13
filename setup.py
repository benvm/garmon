
import os
from babel.messages import frontend as babel

from distutils.core import setup
from distutils import cmd
from distutils.command.install_data import install_data as _install_data
from distutils.command.build import build as _build

import garmon

class build(_build):
    sub_commands = [('compile_catalog', None)] + _build.sub_commands
    def run(self):
        _build.run(self)


class install_data(_install_data):
 
    def run(self):
        for lang in os.listdir('garmon/locale'):
            if os.path.isdir(os.path.join('garmon/locale', lang)):
            	lang_dir = os.path.join('share', 'locale', lang, 'LC_MESSAGES')
            	lang_file = os.path.join('garmon/locale', lang, 'LC_MESSAGES', 'garmon.mo')
            	#self.data_files.append( (lang_dir, [lang_file]) )
        _install_data.run(self)

cmdclass = {
        'build': build,
        'install_data': install_data,
        'compile_catalog': babel.compile_catalog,
        'extract_messages': babel.extract_messages,
        'init_catalog': babel.init_catalog,
        'update_catalog': babel.update_catalog}


setup ( name='garmon',
        version=garmon.version,
        description='GTK OBD-II Scantool',
        author='Ben Van Mechelen',
        author_email='me@benvm.be',
        url='http://github.com/benvm/garmon',
        packages=['garmon',
                  'garmon.plugins',
                  'garmon.plugins.dtc_reader',
                  'garmon.plugins.dtc_clearer',
                  'garmon.plugins.live_data',
                  'garmon.plugins.freeze_frame_data'],
        package_data={'garmon': ['data/*','locale/*/LC_MESSAGES/*.mo'],
                      'garmon.plugins.dtc_reader': ['*.ui'],
                      'garmon.plugins.freeze_frame_data': ['*.ui'],
                      'garmon.plugins.live_data': ['*.ui']},
        scripts=['scripts/garmon',],
        license=garmon.license,
        data_files=[('share/applications', ['garmon.desktop',]),],
        cmdclass = cmdclass,
      )

