# -*- coding: utf-8 -*-
"""
This module contains the tool of slapos.recipe.maarch
"""
import os
from setuptools import setup, find_packages


def read(*rnames):
    return open(os.path.join(os.path.dirname(__file__), *rnames)).read()

version = '0.2'

long_description = read('README.txt') + '\n'

entry_point = 'slapos.recipe.maarch:Recipe'
entry_points = {"zc.buildout": ["default = %s" % entry_point]}

tests_require = ['zope.testing', 'zc.buildout']

setup(name='slapos.recipe.maarch',
      version=version,
      description="",
      long_description=long_description,
      # Get more strings from
      # http://pypi.python.org/pypi?%3Aaction=list_classifiers
      classifiers=[
        'Framework :: Buildout',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        ],
      keywords='',
      author='Marco Mariani',
      author_email='marco.mariani@nexedi.com',
      url='http://git.erp5.org/gitweb/slapos.recipe.maarch.git',
      license='GPLv3',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['slapos', 'slapos.recipe'],
      include_package_data=True,
      zip_safe=False,
      install_requires=['setuptools',
                        'zc.buildout',
                        # -*- Extra requirements: -*-
                        'slapos.cookbook',
                        'psycopg2',
                        ],
      tests_require=tests_require,
      extras_require=dict(tests=tests_require),
      test_suite='slapos.recipe.maarch.tests.test_docs.test_suite',
      entry_points=entry_points,
      )
