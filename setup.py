


import os
from distutils.core import setup

import garmon

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
        package_data={'garmon': ['data/*'],
                      'garmon.plugins.dtc_reader': ['*.ui'],
                      'garmon.plugins.freeze_frame_data': ['*.ui'],
                      'garmon.plugins.live_data': ['*.ui']},
        scripts=['scripts/garmon',],
        license=garmon.license,
        data_files=[('share/applications', ['garmon.desktop',]),],
      )


