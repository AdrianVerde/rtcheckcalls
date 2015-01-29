from twisted.web.resource import Resource
from twisted.web.util import redirectTo

from obelisk import session

from obelisk.model import Model
from obelisk.asterisk.model import SipPeer

from obelisk.templates import print_template
from obelisk.asterisk.users import change_options, get_options
from obelisk.session import get_user
from obelisk.model import Model, User
from obelisk.tools import ticker
import wallet

class OptionsResource(Resource):
    def render_POST(self, request):
	logged = get_user(request)
	if not logged:
		return redirectTo("/", request)
	args = {}
	options = {}
	user_ext = logged.voip_id
        for a in request.args:
            args[a] = request.args[a][0]

	if logged:
		if 'tls' in args and args['tls']:
			options['tls'] = args['tls']
		else:
			options['tls'] = False
		if 'srtp' in args and args['srtp']:
			options['srtp'] = args['srtp']
		else:
			options['srtp'] = False
		options['voicemail'] = args.get('voicemail', False)
		if 'ext' in args and args['ext'] and logged.admin:
			user_ext = args['ext']
		if 'lowquality' in args and args['lowquality']:
			options['codecs'] = ['gsm']
		change_options(user_ext, options)
		return redirectTo('/options/' + user_ext, request)
	return redirectTo('/', request)

    def render_GET(self, request):
	res = None
	logged = session.get_user(request)
	if not logged:
		return redirectTo('/', request)
	parts = request.path.split("/")
	if len(parts) > 2 and logged.admin:
		user_ext = parts[2]
	else:
		user_ext = logged.voip_id
	args = {'ext': user_ext, 'lowquality': '', 'tls': '', 'srtp': '', 'voicemail': ''}
	options = get_options(user_ext)
	if 'codecs' in options and 'gsm' in options['codecs']:
		args['lowquality'] = ' checked '
	if options['tls']:
		args['tls'] = ' checked '
	if options['srtp']:
		args['srtp'] = ' checked '
	if options['voicemail']:
		args['voicemail'] = ' checked '
        model = Model()
        user = model.query(User).filter_by(voip_id=user_ext).first()
        if user and (logged.admin or user.id == logged.id):
            args['bitcoin'] = self.render_btc(logged, user, wallet)
        else:
            return redirectTo('/', request)
	content = print_template('options', args)
        peer = model.query(SipPeer).filter_by(regexten=logged.voip_id).first()
	return print_template('content-pbx-lorea', {'content': content, 'user': logged.voip_id, 'username': peer.name})

    def render_btc(self, logged, user, wallet):
        address = wallet.get_address(user.id)
        qr = ' <a href="https://blockchain.info/qr?data=%s&size=300"><img src="/tpl/images/qr.png" /></a>' % (address,)
        bitcoin = '<b>' + address + '</b>' + qr
        user.update_wallet(Model())
        if user.wallets and (user.wallets[0].received or user.wallets[0].unconfirmed):
            user_wallet = user.wallets[0]
            pending = float(user_wallet.received - user_wallet.accounted)
            bitcoin += "<br />Saldo: %.4f" % (pending,)
            if user_wallet.unconfirmed:
                bitcoin += " (" + str(user_wallet.unconfirmed) + " sin confirmar)"
            if pending > 0:
                bitcoin += "<br />"
                bitcoin += print_template('bitcoin-trade', {'ticker': str(ticker.price),
                                          'pending': str(pending)})
        else:
            bitcoin += '<p>Puedes enviar fondos a la direccion bitcoin de tu cuenta para recargar credito.</p>'
        return bitcoin

    def getChild(self, name, request):
        return self
