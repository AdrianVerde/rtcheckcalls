"""
SSE Resource.

Handles a Server Side Events javascript connection and
allows other parts of the application to send real time
updates through sse.
"""

from twisted.internet.task import deferLater
from twisted.internet import reactor
from twisted.web.resource import Resource
from twisted.web.util import redirectTo
from twisted.web import server

from datetime import datetime
import time
import json

from obelisk.config import config
from obelisk.model import Model, WebSession, User
from obelisk.session import get_session, get_user, get_user_sessions
from obelisk.asterisk import ami
from obelisk.resources import login

resource = None

class SSEConnection(object):
    def __init__(self, request):
        import obelisk.resources.peers
	parts = request.path.split("/")
	if len(parts) > 3:
		user = parts[2]
		password = parts[3]
		login.resource.login(user, password, request)
		print "login", user

	self.request = request
	tcpok = True
	try:
		request.transport.setTcpNoDelay(True)
		request.transport.setTcpKeepAlive(True)
	except:
		# the transport can err if the client is not there any more,
		# don't do anything else if that happens
		tcpok = False

	# get user session
	self.session = get_session(request)
	self.user = get_user(request)

	# send protocol header and starting data
	if tcpok:
		self.send_header(request)
		# no user, no data for now...
		if self.user:
			self.write(time.time(), json.dumps({'user': self.user.voip_id, 'credit':float(self.user.credit)}), 'credit')
			self.write(time.time(), obelisk.resources.peers.resource.get_peers(), 'peers')

    def send_header(self, request):
	"""
	Sets sse headers on a request

	request -- twisted python request
	"""
	request.setHeader('Content-Type', 'text/event-stream')
	request.setHeader('Cache-Control', 'no-cache')
	request.setHeader('Connection', 'keep-alive')

    def write(self, id, msg, section):
	"""
	Send a custom sse event.

	id -- message id
	msg -- data to send, if string, will be sent as is, if other type of
	       object it will be converted to json before sending (must be 
	       serializable to json).
	section -- event name
	"""
	self.request.write("id: %s\n" % (id,))
	self.request.write("event: %s\n" % (section,))
	if msg.__class__ == str:
		self.request.write("data: %s\n\n" % (msg,))
	else:
		self.request.write("data: %s\n\n" % (json.dumps(msg),))

class SSEResource(Resource):
    def __init__(self):
	global resource
	resource = self
	Resource.__init__(self)
	self._connections = {}
	ami.connector.registerEvent('CEL', self.onCelEvent)

    def onCelEvent(self, event):
	"""
	A cel event has arrived, notify clients.

	event -- event data (dict)
	"""
	self.notify(event, 'rtcheckcalls', 'admin')

    def getChild(self, name, request):
	"""
	Return resource children.

	name    -- resource name (str)
	request -- twisted python request
	"""
        return self

    def notify(self, value, section, user):
	"""
	Notify given data event to a user or all users.

	value   -- message payload (string or json serializable object).
	section -- event name.
	user    -- user this event is related to.
	"""
	sessions = []
	if user == 'all':
		sessions = 'all'
	elif user == 'admin':
		sessions = []
	elif user:
		sessions = get_user_sessions(user)
		sessions = map(lambda s: s.session_id, sessions)
	self.notifyChildren(value, section, sessions)

    def notifyChildren(self, value, section='message', sessions=[]):
	"""
	Notify all children of given sessions of some event with data.

	value    -- message payload (string or json serializable object).
	section  -- event name.
	sessions -- sessions to send to.
	"""
	model = Model()
	for req in self._connections.keys():
		if req._disconnected:
			print "sse client disconnected", req
			self._connections.pop(req)
		else:
			conn = self._connections[req]
			web_session = model.query(WebSession).filter_by(session_id=conn.session).first()
			if sessions == 'all' or (conn.session in sessions) or (web_session and web_session.user and web_session.user.admin):
			#if not sessions or (conn.session in sessions) or (web_session and web_session.user and web_session.user.admin):
				if value.__class__ == str:
					conn.write(time.time(), value, section)
				else:
					conn.write(time.time(), json.dumps(value), section)

    def _delayedRender(self, request):
	"""
	Create the sse connection for the request.
	"""
	if not request in self._connections:
		conn = SSEConnection(request)
		self._connections[request] = conn

    def render_GET(self, request):
	"""
	Get response to leave the connection open.

	request -- twisted python request
	"""
	parts = request.path.split("/")
	if len(parts) > 3:
		user = parts[2]
		password = parts[3]
		login.resource.login(user, password, request)
		print "login"
	logged = get_user(request)
	if True or (logged and logged.admin):
		d = deferLater(reactor, 1, lambda: request)
		d.addCallback(self._delayedRender)
		return server.NOT_DONE_YET
	return redirectTo("/", request)

