import os
from twisted.web.server import NOT_DONE_YET
from twisted.web.resource import Resource
from twisted.web.util import redirectTo
from twisted.internet import threads
from datetime import datetime
import csv
import json

from obelisk.accounting import accounting
from obelisk.asterisk.users import parse_users
from decimal import Decimal
from obelisk import charges
from obelisk import calls
from obelisk import session

from obelisk.model import Model, User
from obelisk.asterisk.model import SipPeer

from obelisk.templates import print_template

class UserResource(Resource):
    def __init__(self):
	print "INIT ACCOUNT RESOURCE"
	Resource.__init__(self)
	self._accounting = accounting

    def render_finish(self, output, request):
	request.write(output)
        request.finish()

    def render_thread(self, request, logged):
	logged = session.get_user(request)
        d = threads.deferToThread(self.render_thread, request, logged)
        d.addCallback(self.render_finish, request)
	return NOT_DONE_YET

    def render_GET(self, request):
	logged = session.get_user(request)
        args = {}
        for a in request.args:
            args[a] = request.args[a][0]

	if 'account' in args:
		res = args['account']
	else:
		parts = request.path.split("/")
		if len(parts) > 5 and logged and (logged.voip_id == parts[3] or logged.admin == 1):
			section = parts[2]
			user = parts[3]
			offset = parts[4]
			limit = parts[5]
			if section == 'json':
				return self.render_user_accounting(logged, user, request, offset, limit)
		elif len(parts) > 2:
			user = parts[2]
			if user == 'accounts':
				res = self.render_accounts(request)
			elif logged and (logged.voip_id == user or logged.admin == 1):
				res = self.render_user(user, request)
				return res
			else:
				return redirectTo("/", request)
	if isinstance(res, str):
		return print_template('content-pbx-lorea', {'content': res})
	else:
		return res

    def render_accounts(self, request):
	res = "<h2>accounts</h2>"
	logged = session.get_user(request)
	if not logged or not logged.admin:
		return redirectTo("/", request)
	model = Model()
	all_users = model.query(User)
	total_credit = Decimal()
	for user in all_users:
		ext = user.voip_id
		credit = user.credit
		peer = model.query(SipPeer).filter_by(regexten=ext).first()
		if peer and peer.name:
			username = peer.name
		else:
			username = "desconocido"
		
		res += "<p>%s <a href='/user/%s'>%s</a> %.3f</p>" % (str(ext), str(ext), str(username), credit)
		total_credit += Decimal(credit)
	res += "<p>total credit: %s</p>" % (total_credit,)
	return res

    def render_user_accounting(self, logged, user_ext, request, offset, limit):
	user_calls = json.dumps(calls.get_calls(user_ext, logged, int(limit), int(offset), 'json'))
	request.setHeader('Content-Type', 'application/json')
	return user_calls

    def render_pager(self, user_ext, elements):
	text = ""
	if elements < 10:
		return ""
	iters = range(elements/10)
	if elements%10:
		iters.append(len(iters))
	for i in xrange(elements/10):
		if i == 0:
			selected = "class='row_selected'"
		else:
			selected = ""
		text += "<a id='accounting_%s' %s href='javascript:load_calls(\"%s\",%s,%s)'>%s</a> " % (i, selected, user_ext, i*10, (i+1)*10, i+1)
	return text

    def render_user(self, user_ext, request):
	model = Model()
	peer = model.query(SipPeer).filter_by(regexten=user_ext).first()
	creditlink = ''
	if peer:
		username = peer.name
	else:
		username = user_ext
	user = model.get_user_fromext(user_ext)
	logged = session.get_user(request)
	if user:
		credit = "%.3f" % (user.credit,)
		user_charges = charges.get_charges(user_ext)
		n_calls = len(user.calls)
		pager = self.render_pager(user_ext, n_calls)
		user_calls = calls.get_calls(user_ext, logged, 10) + "<p>%s</p>" % (pager,)

		creditlink = ""
		if user.credit > 0:
			if user.voip_id == logged.voip_id:
				creditlink += '<a href="/credit/transfer">Transferir</a>'
			else:
				creditlink += '<a href="/credit/transfer/%s">Transferir</a>' % (user.voip_id)
		if logged.admin:
			creditlink += ' <a href="/credit/add/%s">Crear</a>' % (user.voip_id)
	else:
		credit = 0.0
		user_charges = ""
		user_calls = ""
	all_calls = self.render_user_calls(user_ext, request)
	args = {'ext': user_ext, 'username': username, 'credit': credit, 'credit_link':creditlink ,'calls': user_calls, 'charges': user_charges, 'all_calls': all_calls}
	return print_template('user-pbx-lorea', args)

    def render_user_calls(self, user_ext, request):
	FILE = "/var/log/asterisk/cdr-csv/Master.csv"
	if not os.path.exists(FILE):
		return
	f = open(FILE)
	csv_file = csv.reader(f)
	data = list(csv_file)
	logged = session.get_user(request)
	model = Model()
	peer = model.query(SipPeer).filter_by(regexten=user_ext).first()
	user_extensions = [user_ext]
	if peer:
		user_extensions.append(peer.name)
	res = ""
	calls = ""
	for a in data:
		if 'queue-multicall' in a:
			continue
		time_1 = a[9]
		time_2 = a[10]
		time_3 = a[11]
		duration = a[12]
		billsecs = int(a[13])
		from_ext = a[1]
		from_name = a[4]
		appdata = a[8]
		status = a[-4]
		id = a[-2]
		delta = 0.0
		#totalsecs += int(billsecs)
		t1 = datetime.strptime(time_1, "%Y-%m-%d %H:%M:%S")
		to_ext = a[2]
		if to_ext.startswith("stdexten-"):
			status = to_ext.split("-")[1]
			to_ext = a[8].split("@")[0]
		if "@" in appdata and "/" in appdata:
			dest = appdata.split("/")[1].split(",")[0]
			to_ext = dest
		if time_3:
			t2 = datetime.strptime(time_3, "%Y-%m-%d %H:%M:%S")
			delta = t2-t1
		if from_ext in user_extensions or to_ext in user_extensions:
			#calls = "<p>[%s] %s to %s for %s secs on %s/%s/%s %s</p>" % (id, from_ext, to_ext, delta, t1.day, t1.month, t1.year, status) + calls
			date = "%s/%s/%s" % (t1.day, t1.month, t1.year)
			if not from_ext in user_extensions and logged.admin:
				from_ext = "<a href='/user/%s'>%s</a>" % (from_ext, from_ext)
			if not to_ext in user_extensions and logged.admin:
				to_ext = "<a href='/user/%s'>%s</a>" % (to_ext, to_ext)
			calls = ("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (date, from_ext, to_ext, delta, status)) + calls

		#if status == "ANSWERED" and (billsecs > umbra or not umbra):
		#	print from_ext,"->"," "*(14-len(a[2]))+a[2]+" ["+str(billsecs)+"]\t"+str(t1.day)+"\t"+str(t1.hour)
	res += calls
	return res
    def getChild(self, name, request):
        return self

