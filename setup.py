from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='use-free-images',

    version='1.0.0',

    description=('Bulk download URL and copyright information about images '
                 'from Flickr, FreeImages.com and MorgueFile'),
    long_description=long_description,

    url='https://github.com/jakubvalenta/use-free-images',

    author='Jakub Valenta',
    author_email='jakub@jakubvalenta.cz',

    license='Apache Software License',

    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Topic :: Software Development',
        'Programming Language :: Python :: 3',
    ],

    keywords='',

    packages=find_packages(),

    install_requires=[
        'beautifulsoup4',
        'flickrapi',
        'listio',
        'requests',
    ],

    entry_points={
        'console_scripts': [
            'use-free-images=use_free_images.use_free_images:main',
        ],
    },
)
