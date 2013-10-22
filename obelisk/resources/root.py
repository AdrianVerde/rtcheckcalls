import os

from twisted.web.resource import Resource
from twisted.web.static import File
from twisted.web.wsgi import WSGIResource
from twisted.internet import reactor
from twisted.web.util import redirectTo, Redirect
from twisted.python import log

from obelisk.resources.peers import PeersResource
from obelisk.resources.user import UserResource
from obelisk.resources.prices import PricesResource
from obelisk.resources.login import LoginResource
from obelisk.resources.stats import StatsResource
from obelisk.resources.logout import LogoutResource
from obelisk.resources.providers import ProvidersResource
from obelisk.resources.calls import CallsResource
from obelisk.resources.sse import SSEResource
from obelisk.resources.credit import CreditResource
from obelisk.resources.register import RegisterResource
from obelisk.resources.options import OptionsResource
from obelisk.resources.changepass import ChangePassResource
from obelisk.resources.docs import DocsResource
from obelisk.resources.voicemail import VoiceMailResource
from obelisk.resources.admin import AdminResource
from obelisk.resources.tinc import TincResource
from obelisk.resources.dundi import DundiResource
from obelisk.resources.pln import PLNResource
from obelisk.resources.btcin import BtcInResource
from obelisk.templates import print_template
from obelisk.pricechecker import get_winners

from obelisk.rtcheckcalls import CallManager
from obelisk.asterisk import ami, cli

from obelisk.testchannels import TestChannels
from obelisk.resources import sse
from obelisk.tools import ticker, host_info, mailing

from obelisk import session

import obelisk

class RootResource(Resource):
    def __init__(self):
        self.alarm_set = False
        Resource.__init__(self)
	ami.connect()
	self.call_manager = CallManager()
	our_dir = os.path.dirname(os.path.dirname(obelisk.__file__))
	ami.connector.registerEvent('CEL', self.call_manager.on_event)
        self.putChild("voip", PeersResource())
        self.putChild("prices", PricesResource())
        self.putChild("voicemail", VoiceMailResource())
        self.putChild("user", UserResource())
        self.putChild("sse", SSEResource())
        self.putChild("calls", CallsResource())
        self.putChild("password", ChangePassResource())
        self.putChild("credit", CreditResource())
        self.putChild("register", RegisterResource())
        self.putChild("options", OptionsResource())
        self.putChild("stats", StatsResource())
        self.putChild("providers", ProvidersResource())
        self.putChild("login", LoginResource())
        self.putChild("logout", LogoutResource())
        self.putChild("admin", AdminResource())
        self.putChild("docs", DocsResource())
        self.putChild("icons", File("/usr/share/icons"))
        self.putChild("tpl", File(os.path.join(our_dir, "templates")))
        self.putChild("sip", File("/home/lluis/tst_sip_gui"))
        self.putChild("jssip", File("/home/caedes/jssip"))
        self.putChild("favicon.ico", File(os.path.join(our_dir, "templates", "telephone_icon.ico")))
        self.putChild("tinc", TincResource())
        self.putChild("dundi", DundiResource())
        self.putChild("pln", PLNResource())
        self.putChild("btcin", BtcInResource())
	if 'pln' in obelisk.config.config:
		pln_name = obelisk.config.config['pln']['name']
		self.putChild(pln_name, Redirect('/tinc/pubkey'))
		self.putChild(pln_name +'.pub', Redirect('/dundi/pubkey'))
	self.putChild('node.json', Redirect('/pln/node.json'))

	reactor.callLater(2, reactor.callInThread, self.get_winners)
	#reactor.callLater(4, reactor.callInThread, self.get_channel_test)
        reactor.callLater(10, self.monitor_thread)
	#self.channel_tester = TestChannels()
        # start running the ticker
        ticker.ticker()

    def run_alarms(self, reason, nclients, nproc):
        log.err("%s (%s/128) (%s)" % (reason, nclients, nproc), system='CLI,monitor')
        if not self.alarm_set:
            log.msg("Running alarms", system='CLI,monitor')
            self.alarm_set = True
            # restart asterisk, should check if there are ongoing calls
            host_info.generate_logs()
            host_info.asterisk_restart()
            mailing.admin_send('Asterisk restarted', 'Restarted due to critical number of cli connections %s %s' % (nclients, nproc))
            #ext = obelisk.config.config.get('alert-extension', '501@from-payuser')
            #for name in obelisk.config.config.get('alert', []):
            #    name = str(name)
            #    log.msg("Calling %s" % (name,), system='CLI,monitor')
            #    if len(name) > 2:
            #        cli.run_command("channel originate SIP/%s extension %s" % (name, ext))

    def monitor_thread(self):
        nclients = host_info.get_cli_clients()
        nproc = host_info.get_asterisk_processes()
	if nclients < 7:
            self.alarm_set = False
            log.msg("%s (%s/128) (%s)" % ('Ok', nclients, nproc), system='CLI,monitor')
	elif nclients < 10:
            log.msg("%s (%s/128) (%s)" % ('Danger', nclients, nproc), system='CLI,monitor')
	elif nclients < 20:
            self.run_alarms('Warning', nclients, nproc)
	elif nclients < 80:
            self.run_alarms('Critical', nclients, nproc)
	else:
            self.run_alarms('Possibly Dead', nclients, nproc)
	reactor.callLater(120, self.monitor_thread)

    def get_winners(self):
	get_winners()
	reactor.callLater(600, reactor.callInThread, self.get_winners)

    def get_channel_test(self):
	test = self.channel_tester.get_rates()
	if test:
		reactor.callFromThread(sse.resource.notify, test, 'channels', 'all')
	reactor.callLater(5, reactor.callInThread, self.get_channel_test)

    def getChild(self, name, request):
        return self

    def render_GET(self, request):

	output = "<li><a href='/prices'>precios</a></li>"
	output += "<li><a href='/docs'>documentacion</a></li>"

	user = session.get_user(request)
        main_page = print_template('portada', {})
	if user:
		user_ext = user.voip_id
		output_user = "<li><a href='/user/"+user.voip_id+"'>datos usuario</a></li>"
		output_user += "<li><a href='/voip'>listin telefonico</a></li>"
		output_user += "<li><a href='/stats'>estadisticas</a></li>"
		if user.admin == 1:
			output_user += "<li><a href='/admin'>admin</a></li>"
			user_ext += " eres admin"
		output_user += "<li><a href='/logout'>logout</a></li>"

	        return print_template('logged-pbx-lorea', {'LINKS':output, 'LOGGED_LINKS':output_user, 'user': user_ext, 'content': main_page})
	else:
		output += "<li><a href='/register'>registrarse</a></li>"
	        return print_template('home-pbx-lorea', {'LINKS':output, 'content': main_page})

    def render_POST(self, request):
	return "<p>xxxxx</p>"
        #return redirectTo("pylibrarian.py", request)

