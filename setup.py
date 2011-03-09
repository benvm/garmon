


import os
from distutils.core import setup

import garmon

setup ( name='garmon',
        version=garmon.version,
        description='GTK OBD-II Scantool',
        author='Ben Van Mechelen',
        author_email='me@benvm.be',
        url='http://github.com/benvm/garmon',
        packages=['garmon',],
        package_data={'garmon': ['data/*']},
        scripts=['scripts/garmon',],
        license=garmon.license,
        data_files=[('share/applications', ['garmon.desktop',]),],
      )


