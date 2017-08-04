import os
import sys
from setuptools import setup

MIN_PYTHON = (3, 0)
if sys.version_info < MIN_PYTHON:
    sys.stderr.write("Python {}.{} or later is required\n".format(*MIN_PYTHON))
    sys.exit(1)


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name='osrm-py',
    version='0.4',
    author='Alexander Verbitsky',
    author_email='habibutsu@gmail.com',
    maintainer='Alexander Verbitsky',
    maintainer_email='habibutsu@gmail.com',
    description='Python client for OSRM API',
    long_description=read('README.rst'),
    keywords='osrm',
    url='https://github.com/gojuno/osrm-py',
    py_modules=['osrm'],
    test_suite='test',
    extras_require={
        'aiohttp': (
            'aiohttp>=1.2.0,<=2.1.0',
        ),
        'requests': (
            'requests>=2.14.0',
        ),
    },
    license='BSD',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Topic :: Utilities',
        'Programming Language :: Python',
        'License :: OSI Approved :: BSD License',
    ],
)
