# -*- coding: utf-8 -*-
'''
Created on 19.10.2012

@author: Tobias Schaefer
'''

from trac.core import Component,implements
from trac.db import DatabaseManager
from trac.env import IEnvironmentSetupParticipant
from trac.versioncontrol.api import IRepositoryChangeListener

import db_default
import re

class TicketModifiedFilesSystem(Component):
    implements(IEnvironmentSetupParticipant, IRepositoryChangeListener)
    """Central functionality for the TicketModifiedFiles plugin."""

    _last_cset_id = None

    TICKET_RE = re.compile(r'#([0-9]+)')

    # IEnvironmentSetupParticipant methods
    def environment_created(self):
        self.found_db_version = 0
        self.upgrade_environment(self.env.get_read_db())

    def environment_needs_upgrade(self, db):
        cursor = db.cursor()
        cursor.execute("SELECT value FROM system WHERE name=%s", (db_default.name,))
        value = cursor.fetchone()
        if not value:
            self.found_db_version = 0
            return True
        else:
            self.found_db_version = int(value[0])
            self.log.debug('TicketModifiedFiles: Found db version %s, current is %s' % (self.found_db_version, db_default.version))
            if self.found_db_version < db_default.version:
                return True
                
        # Fall through
        return False

    def upgrade_environment(self, db):
        db_manager, _ = DatabaseManager(self.env)._get_connector()
                
        # Insert the default table
        old_data = {} # {table_name: (col_names, [row, ...]), ...}
        cursor = db.cursor()
        if not self.found_db_version:
            cursor.execute("INSERT INTO system (name, value) VALUES (%s, %s)",(db_default.name, db_default.version))
        else:
            cursor.execute("UPDATE system SET value=%s WHERE name=%s",(db_default.version, db_default.name))
            for tbl in db_default.tables:
                try:
                    cursor.execute('SELECT * FROM %s'%tbl.name)
                    old_data[tbl.name] = ([d[0] for d in cursor.description], cursor.fetchall())
                    cursor.execute('DROP TABLE %s'%tbl.name)
                except Exception, e:
                    if 'OperationalError' not in e.__class__.__name__:
                        raise e # If it is an OperationalError, just move on to the next table
                            
                
        for tbl in db_default.tables:
            for sql in db_manager.to_sql(tbl):
                cursor.execute(sql)
                    
            # Try to reinsert any old data
            if tbl.name in old_data:
                data = old_data[tbl.name]
                sql = 'INSERT INTO %s (%s) VALUES (%s)' % \
                      (tbl.name, ','.join(data[0]), ','.join(['%s'] * len(data[0])))
                for row in data[1]:
                    try:
                        cursor.execute(sql, row)
                    except Exception, e:
                        if 'OperationalError' not in e.__class__.__name__:
                            raise e

    # IRepositoryChangeListener
    # used to hook on repository commits
    def changeset_added(self, repos, revision):
        if self._is_duplicate(revision):
            return
        tickets = self._parse_message(revision.message)
        
        self._save_ticket_references(repos, revision, tickets)

    def _is_duplicate(self, changeset):
        # Avoid duplicate changes with multiple scoped repositories
        # TODO: hier eher test, ob changeset schon in meiner Tabelle vorhanden?
        cset_id = (changeset.rev, changeset.message, changeset.author, changeset.date)
        if cset_id != self._last_cset_id:
            self._last_cset_id = cset_id
            return False
        return True

    def _parse_message(self, message):
        """Parse the commit message and return the ticket references."""
        return self.TICKET_RE.findall(message)

    def _save_ticket_references(self, repos, revision, tickets):
        """Saves the ticket references by revision."""

        @self.env.with_transaction()
        def do_save(db):
            cursor = db.cursor()
            
            for ticket in tickets:
                try:
                    cursor.execute("""
                        INSERT INTO ticketmodifiedfiles (repos, rev, ticket)
                        VALUES(%s, %s, %s)
                        """, (repos.id, revision.rev, ticket))
                except Exception, e:
                    # catch duplicate key errors and ignore them
                    if 'IntegrityError' not in e.__class__.__name__:
                        raise e
