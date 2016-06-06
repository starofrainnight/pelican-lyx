#!/usr/bin/env python

from pydgutils_bootstrap import use_pydgutils
use_pydgutils()

import pydgutils
import sys
from setuptools import setup, find_packages

package_name = "pelican-lyx-reader"

source_dir = pydgutils.process()

packages = find_packages(where=source_dir)

long_description=(
     open("README.rst", "r").read()
     + "\n" +
     open("CHANGES.rst", "r").read()
     )

install_requires = []

setup(
    name=package_name,
    version="0.0.1",
    author="Hong-She Liang",
    author_email="starofrainnight@gmail.com",
    url="https://github.com/starofrainnight/%s" % package_name,
    description="A lyx reader plugin for pelican",
    long_description=long_description,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3",
        'Topic :: Text Processing :: Markup'
    ],
    install_requires=install_requires,
    package_dir = {"": source_dir},
    packages=packages,
    # If we don"t set the zip_safe to False, pip can"t find us.
    zip_safe=False,
    )
