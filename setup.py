#!/usr/bin/env python

from distutils.core import setup

setup(name='gmc_ims',
      version='0',
      description='',
      url='https://github.com/dW5kZWFk/ims',
      scripts=['wsgi.py'],
      packages=['application',
                'application.auth',
                'application.category',
                'application.customer',
                'application.home',
                'application.inventory',
                'application.purchase_sale',
                'application.repair',
                'application.service',
                'application.static',
                'application.templates',
                'application.upload',
                'application.warehouse',
                ],
      package_dir={ 'application': 'application' },
      include_package_data=True,
     )
