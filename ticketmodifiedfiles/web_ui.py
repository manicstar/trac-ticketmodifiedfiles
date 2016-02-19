# -*- coding: utf-8 -*-
# TicketModifiedFiles plugin
# This software is licensed as described in the file COPYING.txt, which you
# should have received as part of this distribution.

import re

from trac.core import Component,implements
from trac.ticket.model import Ticket
from trac.web import IRequestHandler
from trac.web.api import IRequestFilter
from trac.web.chrome import ITemplateProvider, add_stylesheet, add_script, add_ctxtnav
from trac.util.datefmt import format_time
from trac.config import ListOption
from pkg_resources.ResourceManager import resource_filename

from genshi.filters import Transformer
from genshi.builder import tag

'''
TODO:
 - ...
'''
class TicketModifiedFilesPlugin(Component):
    implements(IRequestHandler, IRequestFilter, ITemplateProvider)
    
    TMF_RE = re.compile(r'/modifiedfiles/([0-9]+)$', re.U)
    TICKET_RE = re.compile(r'#([0-9]+)', re.U)
    
    ignored_statuses = ListOption('modifiedfiles', 'ignored_statuses',
                                  default='closed', 
                                  doc="Statuses to ignore when looking for conflicting tickets")

    # IRequestHandler methods
    def match_request(self, req):
        match = self.TMF_RE.match(req.path_info)
        if match:
            req.args['ticket_id'] = match.group(1)
            return True
    
    def process_request(self, req):
        #Retrieve the information needed to display in the /modifiedfiles/ page
        (ticket_id, files, deletedfiles, ticketsperfile, filestatus, conflictingtickets, ticketisclosed, revisions, ticketsdescription) = self.__process_ticket_request(req)
        #Pack the information to send to the html file
        data = {'ticketid':ticket_id,
                'files':files,
                'deletedfiles':deletedfiles,
                'ticketsperfile':ticketsperfile,
                'filestatus':filestatus,
                'conflictingtickets':conflictingtickets,
                'ticketisclosed':ticketisclosed,
                'revisions':revisions,
                'ticketsdescription':ticketsdescription}

        add_ctxtnav(req, 'Back to Ticket #%s' % ticket_id, req.href.ticket(ticket_id))

        #Add the custom stylesheet
        add_stylesheet(req, 'common/css/timeline.css')
        add_stylesheet(req, 'tmf/css/ticketmodifiedfiles.css')
        add_script(req, 'tmf/js/ticketmodifiedfiles.js')
        return 'ticketmodifiedfiles.html', data, None
    
    # IRequestFilter methods
    def pre_process_request(self, req, handler):
        return handler
    
    def post_process_request(self, req, template, data, content_type):
        if template == "ticket.html":
            add_ctxtnav(req, "Modified Files", req.href.modifiedfiles(req.args.get('id')))
        return template, data, content_type

    # ITemplateProvider methods
    def get_templates_dirs(self):
        """Return a list of directories containing the provided template
        files.
        """
        return [resource_filename(__name__, 'templates')]
    
    def get_htdocs_dirs(self):
        """Return a list of directories with static resources (such as style
        sheets, images, etc.)

        Each item in the list must be a `(prefix, abspath)` tuple. The
        `prefix` part defines the path in the URL that requests to these
        resources are prefixed with.

        The `abspath` is the absolute path to the directory containing the
        resources on the local file system.
        """
        return [('tmf', resource_filename(__name__, 'htdocs'))]

    # Internal methods
    def __process_ticket_request(self, req, justnumconflictingtickets = False):
        ticket_id = int(req.args.get('ticket_id'))
        req.perm('ticket', ticket_id, None).require('TICKET_VIEW')
        
        #Check if the ticket exists (throws an exception if the ticket does not exist)
        thisticket = Ticket(self.env, ticket_id)
        
        files = []
        revisions = []
        ticketsperfile = {}
        
        db = self.env.get_read_db()
        cursor = db.cursor()
        #Retrieve all the revisions which's messages contain "#<TICKETID>"
        cursor.execute("SELECT rev, time, author, message FROM revision WHERE message LIKE '%%#%s%%'" % ticket_id)
        repos = self.env.get_repository()
        for rev, time, author, message, in cursor:
            #Filter out non-related revisions.
            #for instance, you are looking for #19, so you don't want #190, #191, #192, etc. to interfere
            #To filter, check what the eventual char after "#19" is.
            #If it's a number, we dont' want it (validrevision = False), but if it's text, keep this revision
            validrevision = True
            tempstr = message.split("#" + str(ticket_id), 1)
            if len(tempstr[1]) > 0:
                try:
                    int(tempstr[1][0])
                    validrevision = False
                except:
                    pass
                
            if validrevision:
                date = "(" + format_time(time, str('%d/%m/%Y - %H:%M')) + ")"
                revisions.append((int(rev), author, date))
                for node_change in repos.get_changeset(rev).get_changes():
                    files.append(node_change[0])
                    
        
        #Remove duplicated values
        files = self.__remove_duplicated_elements_and_sort(files)
        
        filestatus = {}
        
        for file in files:
            #Get the last status of each file
            try:
                node = repos.get_node(file)
                filestatus[file] = node.get_history().next()[2]
            except:
                #If the node doesn't exist (in the last revision) it means that it has been deleted
                filestatus[file] = "delete"
        
            #Get the list of conflicting tickets per file
            tempticketslist = []
            cursor.execute("SELECT message FROM revision WHERE rev IN (SELECT rev FROM node_change WHERE path='%s')" % file)
            for message, in cursor:
                #Extract the ticket number
                # TODO: konstante einsetzen
                match = re.search(r'#([0-9]+)', message)
                if match:
                    ticket = int(match.group(1))
                    #Don't add yourself
                    if ticket != ticket_id:
                        tempticketslist.append(ticket)
            tempticketslist = self.__remove_duplicated_elements_and_sort(tempticketslist)
            
            ticketsperfile[file] = []
            #Keep only the active tickets
            for ticket in tempticketslist:
                try:
                    if Ticket(self.env, ticket)['status'] not in self.ignored_statuses:
                        ticketsperfile[file].append(ticket)
                except:
                    pass
        
        #Get the global list of conflicting tickets
        #Only if the ticket is not already closed
        conflictingtickets=[]
        ticketsdescription={}
        ticketsdescription[ticket_id] = thisticket['summary']
        ticketisclosed = True
        if thisticket['status'] not in self.ignored_statuses:
            ticketisclosed = False
            for fn, relticketids in ticketsperfile.items():
                for relticketid in relticketids:
                    tick = Ticket(self.env, relticketid)
                    conflictingtickets.append((relticketid, tick['status'], tick['owner']))
                    ticketsdescription[relticketid] = tick['summary']
    
            #Remove duplicated values
            conflictingtickets = self.__remove_duplicated_elements_and_sort(conflictingtickets)
        
        #Close the repository
        repos.close()
        
        #Separate the deleted files from the others
        deletedfiles = []
        for file in files:
            if filestatus[file] == "delete":
                deletedfiles.append(file)
        for deletedfile in deletedfiles:
            files.remove(deletedfile)
        
        #Return all the needed information
        return (ticket_id, files, deletedfiles, ticketsperfile, filestatus, conflictingtickets, ticketisclosed, revisions, ticketsdescription)
    
    def __remove_duplicated_elements_and_sort(self, ticket_list):
        d = {}
        for x in ticket_list: d[x]=1
        return sorted(d.keys())
