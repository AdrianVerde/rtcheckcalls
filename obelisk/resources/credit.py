from twisted.web.resource import Resource
from twisted.web.util import redirectTo
import subprocess

from obelisk.accounting import accounting
from decimal import Decimal
from obelisk import session

from obelisk.model import Model

from obelisk.templates import print_template

class CreditResource(Resource):
    def __init__(self):
	Resource.__init__(self)

    def render_POST(self, request):
	return self.render_GET(request)

    def render_GET(self, request):
	res = None
	logged = session.get_user(request)

	parts = request.path.split("/")
	if len(parts) > 2:
		section = parts[2]
		if section in ['add', 'transfer'] and logged:
			res = self.credit_request(section, request, logged)
	if not res:
		return redirectTo("/", request)
	elif isinstance(res, str):
		return print_template('content-pbx-lorea', {'content': res})
	else:
		return res

    def credit_request(self, section, request, logged):
	args = {'user': ""}
	parts = request.path.split("/")
	if len(parts) > 3:
		args['user'] = parts[3]
        for a in request.args:
            args[a] = request.args[a][0]
	if 'user' in args and args['user'] and 'credit' in args and args['credit']:
		try:
			credit = float(args['credit'])
		except:
			return redirectTo(request.path, request)
		if section == 'add' and logged.admin:
			user_ext = self.add_credit(logged, [args['user'], args['credit']])
			return redirectTo("/user/" + user_ext, request)
		elif section == 'transfer':
			self.transfer_credit(logged, [args['user'], args['credit']])
			return redirectTo("/user/" + logged.voip_id, request)
	else:
		return self.credit_form(logged, section, args['user'])

    def credit_form(self, logged, section, user_ext):
	if section == 'transfer':
		res = "<h1>Tranferir credito</h1>"
		res += "<h1>Tu saldo es %.3f" % (float(logged.credit),)
	else:
		res = "<h1>Recargar credito</h1>"
	res += print_template('credit', {'section': section, 'ext': user_ext})
	return res

    def transfer_credit(self, logged, args):
	user = args[0]
	credit = Decimal(args[1])
	return accounting.transfer_credit(logged, user, credit)

    def add_credit(self, logged, args):
	user = args[0]
	credit = Decimal(args[1])
	return accounting.add_credit(logged, user, credit)

    def getChild(self, name, request):
        return self

