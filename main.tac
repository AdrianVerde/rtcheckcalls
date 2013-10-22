import sys

from twisted.web import server
from twisted.internet import reactor
from twisted.application import service, strports
from twisted.python.log import ILogObserver, FileLogObserver

import obelisk
from obelisk.resources.root import RootResource

ignored_logs = ['HTTPChannel', 'HTTPPageGetter', '-']
port = obelisk.config.config.get('port', 8080)

class NoHTTPLogFileObserver(FileLogObserver):
    def emit(self, eventDict):
        system = eventDict.get('system','')
        is_error = eventDict.get('isError', False)
        if is_error or not system.split(',')[0] in ignored_logs:
            eventDict['system'] = system.replace('PersistentAMIProtocol,client', 'AMI')
            return FileLogObserver.emit(self, eventDict)

# Create the root resource
toplevel = RootResource()

# Hooks for twistd
application = service.Application('Voip Manager')
application.setComponent(ILogObserver, NoHTTPLogFileObserver(sys.stdout).emit)

server = strports.service('tcp:'+str(port), server.Site(toplevel))
server.setServiceParent(application)
