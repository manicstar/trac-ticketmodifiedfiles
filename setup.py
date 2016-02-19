#!/usr/bin/env python
from setuptools import setup

setup(
    name='TicketModifiedFiles',
    version='2.0',
    description='Trac plugin that lists the files that have been modified while resolving a ticket.',
    author='Emilien Klein',
    author_email='Emilien Klein <e2jk AT users DOT sourceforge DOT net>',
    maintainer='Tobias Schaefer',
    maintainer_email='schaefer@secdtp.de',
    license='BSD-ish (see the COPYING.txt file)',
    url='http://trac-hacks.org/wiki/TicketModifiedFilesPlugin',
    
    install_requires=['Genshi>=0.6', 'Trac >= 0.12'],
    packages=['ticketmodifiedfiles'],
    package_data={'ticketmodifiedfiles': ['templates/*.html', 'htdocs/css/*.css', 'htdocs/js/*.js']},

    entry_points = {
        'trac.plugins': [
            'ticketmodifiedfiles.web_ui = ticketmodifiedfiles.web_ui',
            'ticketmodifiedfiles.api = ticketmodifiedfiles.api',
        ]
    },
)
