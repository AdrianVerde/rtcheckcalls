from twisted.web.server import NOT_DONE_YET
from twisted.web.resource import Resource
from twisted.internet import threads
import subprocess
from datetime import datetime

from obelisk.asterisk.prefixes import list_prices_json
from obelisk.prices import check_prices
from obelisk.templates import print_template
from obelisk import session

class PricesResource(Resource):
    def render_GET(self, request):
	logged = session.get_user(request)
        d = threads.deferToThread(self.render_thread, request, logged)
        d.addCallback(self.render_finish, request)
	return NOT_DONE_YET

    def render_thread(self, request, logged):
	parts = request.path.split("/")
	if len(parts) > 2 and logged and logged.admin:
		section = parts[2]
		if section == 'check':
			output = check_prices()
			return print_template('content-pbx-lorea', {'content': "<pre>"+output+"</pre>"})
	res = list_prices_json()
	check_link = ""
	if logged and logged.admin:
		check_link = "<p><a href='/prices/check'>Chequear precios</a></p>"
	return print_template('prices-pbx-lorea', {'links': check_link, 'prices': res, 'map': print_template('prices-map-pbx-lorea', {})})

    def render_finish(self, output, request):
	request.write(output)
        request.finish()

    def getChild(self, name, request):
        return self
