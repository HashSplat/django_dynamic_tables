"""
    setup.py - Setup file to distribute the library

See Also:
    https://github.com/pypa/sampleproject
    https://packaging.python.org/en/latest/distributing.html
    https://pythonhosted.org/an_example_pypi_project/setuptools.html
"""
import os
import glob

from setuptools import setup, find_packages


def read(fname):
    """Read in a file"""
    with open(os.path.join(os.path.dirname(__file__), fname), "r") as file:
        return file.read()


# ========== Requirements ==========
def check_options(line, options):
    if line.startswith('--'):
        opt, value = line.split(' ')
        opt = opt.strip()
        value = value.strip()
        try:
            options[opt].append(value)
        except KeyError:
            options[opt] = [value]
        return True


def parse_requirements(filename, options=None):
    """load requirements from a pip requirements file """
    if options is None:
        options = {}
    lineiter = (line.strip() for line in open(filename))
    return [line for line in lineiter if line and not line.startswith("#") and not check_options(line, options)]


requirements = parse_requirements('requirements.txt')
# ========== END Requirements ==========


if __name__ == "__main__":
    setup(
        name="django_dynamic_tables",
        version="0.0.2",
        description="A quick way to add sortable paginated tables with ajax support.",
        url="https://github.com/justengel/django_dynamic_tables",
        download_url="https://github.com/justengel/django_dynamic_tables/archive/v0.0.2.tar.gz",

        author="Justin Engel",
        author_email="jtengel08@gmail.com",

        license="",

        platforms="any",
        classifiers=["Programming Language :: Python",
                     "Programming Language :: Python :: 3",
                     "Operating System :: OS Independent"],

        scripts=[],

        long_description=read("README.md"),
        packages=["dynamic_tables"],
        install_requires=requirements,

        include_package_data=True,

        # package_data={
        #     'package': ['file.dat']
        # }

        # options to install extra requirements
        # extras_require={
        #     'dev': [],
        #     'test': ['converage'],
        # }

        # Data files outside of packages
        # data_files=[('my_data', ["data/my_data.dat"])],

        # keywords='sample setuptools development'

        # entry_points={
        #     'console_scripts': [
        #         'foo = my_package.some_module:main_func',
        #         'bar = other_module:some_func',
        #     ],
        #     'gui_scripts': [
        #         'baz = my_package_gui:start_func',
        #     ]
        # }
    )
