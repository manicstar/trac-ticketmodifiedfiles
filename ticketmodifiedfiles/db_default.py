# -*- coding: utf-8 -*-
'''
Created on 19.10.2012

@author: schaefer
'''

from trac.db import Table, Column

name = 'ticketmodifiedfiles'
version = 1
tables = [
    Table('ticketmodifiedfiles', key=('repos', 'rev', 'ticket'))[
        Column('repos', type='int'),
        Column('rev', key_size=20),
        Column('ticket', type='int'),
    ],
]
