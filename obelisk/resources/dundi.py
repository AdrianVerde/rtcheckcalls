import os

from twisted.internet import reactor
from twisted.web.resource import Resource
from twisted.web.util import redirectTo
from twisted.web.server import NOT_DONE_YET

from obelisk import session
from obelisk.templates import print_template
from obelisk.asterisk import cli
from obelisk.asterisk.dundi import Dundi
from obelisk.tools import html
from obelisk.tools.htmltool import ok_icon, format_ping
from ping import do_one

import obelisk

class DundiResource(Resource):
    def __init__(self):
        Resource.__init__(self)
	self.dundi = Dundi()
        #self.putChild("voip", PeersResource())

    def getChild(self, name, request):
        return self

    def render_GET(self, request):
	parts = request.path.split('/')
	if len(parts) > 2 and parts[2] == 'pubkey':
		return self.dundi.get_public_key()
	user = session.get_user(request)
	if user and user.admin:
        	reactor.callInThread(self.render_dundi_thread, request)
		return NOT_DONE_YET
	else:
		return redirectTo("/", request)

    def render_dundi_thread(self, request):
	content = self.render_dundi(request)
        result = print_template('content-pbx-lorea', {'content': content})
        reactor.callFromThread(self.render_dundi_finish, request, result)

    def render_dundi_finish(self, request, output):
	request.write(output)
        request.finish()

    def render_dundi(self, request):
	d = self.dundi
	connections = d.parse_connections()
	output = "<h2>Dundi</h2>\n"
	output += "<h3>Server</h3>\n"
	output += "<p><b>geo</b>: %s <b>nongeo</b>: %s</p>\n" % (str(d.geo), str(d.nongeo))
	for key in ['locality', 'organization', 'entityid', 'email']:
		val = d.config['general'][key]
		output += '<p><b>%s:</b> %s</p>\n' % (key, val)
	output += "<h3>Peers</h3>\n"
	output += self.render_dundipeers(request, d.find_hosts(), connections)
	return output

    def render_dundipeers(self, request, peers, connections):
	res = [['name', 'address', 'nongeo', 'alias', 'signal']]
	for name, node in peers.iteritems():
		address = node.get('host', '')
		nongeo = str(node.get('nongeo', ''))
		alias = str(node.get('inkey', ''))
		online = 'no'
		if address and address in connections:
			ping = connections[address]['ping']
			online = format_ping(ping)
		res.append([name, address, nongeo, alias, online])
	return html.format_table(res)

