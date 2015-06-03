#!/usr/bin/env python

import os

from ez_setup import use_setuptools

use_setuptools()

from setuptools import setup
from setuptools import find_packages

about = {}
with open(os.path.join("duplicateimagefinder", "__init__.py")) as fp:
    exec(fp.read(), about)

setup(name=about["__title__"],
      version=about["__version__"],
      description=about["__summary__"],
      author=about["__author__"],
      author_email=about["__email__"],
      url=about["__uri__"],
      install_requires=[
          'Pillow>=2.8',
          'tqdm>=1.0',
          'blitzdb==0.2.12',
          'six==1.9.0'],
      packages=find_packages(),
      entry_points={
          'console_scripts': [
              'app = duplicateimagefinder.app:main',
          ],
      },
)
