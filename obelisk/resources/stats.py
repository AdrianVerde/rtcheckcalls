from twisted.web.resource import Resource
from twisted.web.util import redirectTo
from twisted.internet import threads
from twisted.web.server import NOT_DONE_YET

from datetime import datetime

import json
from sqlalchemy import and_, func
import time
import math
from decimal import Decimal

from obelisk.config import config
from obelisk.model import Model, WebSession, User, Call, Charge, Wallet
from obelisk.templates import print_template
from obelisk.tools import host_info
from obelisk import session

class StatsResource(Resource):
    def __init__(self):
	Resource.__init__(self)

    def getChild(self, name, request):
        return self

    def render_finish(self, output, request):
	request.write(output)
        request.finish()

    def render_GET(self, request):
	logged = session.get_user(request)
        d = threads.deferToThread(self.render_thread, request, logged)
        d.addCallback(self.render_finish, request)
	return NOT_DONE_YET

    def render_thread(self, request, logged):
	parts = request.path.split("/")
	if len(parts) > 3:
		section = parts[2]
		type = parts[3]
		c = ""
		o = Call
		if type == 'minutes':
			c = self.sum_minutes
		elif type == 'credit':
			c = self.sum_credit
		elif type == 'charges':
			c = self.sum_charges
			o = Charge
		else:
			return ""
		if section == 'hourly':
			return self.minutes_stats(request, 60*60, 24, c, o)
		if section == 'daily':
			return self.minutes_stats(request, 60*60*24, 10, c, o)
		elif section == 'weekly':
			return self.minutes_stats(request, 60*60*24*7, 10, c, o)
		elif section == 'monthly':
			return self.minutes_stats(request, 60*60*24*30, 10, c, o)
	else:
		if len(parts) > 2:
			section = parts[2]
			if section == 'host':
				content = host_info.get_report()
				return print_template("content-pbx-lorea", {'content': content})
		general_stats = self.general_stats()
		if logged and logged.admin:
			general_stats += "<p><a href='/stats/host'>host stats</a><br /><a href='/providers'>provider stats</a></p>"
		return print_template("graphs", {'stats': general_stats})

        return request.path

    def sum_credit(self, calls):
	cost = 0.0
	benefit = 0.0
	for call in calls:
		if call.rate:
			minutes = math.ceil(call.duration/60.0)
			call_benefit = minutes * 0.001 + 0.001
			cost += float(call.cost)-call_benefit
			benefit += call_benefit
	return cost, benefit

    def sum_minutes(self, calls):
	free = 0
	cost = 0
	pln = 0
	sip = 0
	direct = 0
	for call in calls:
		dest = call.destination
		if dest.isdigit() and len(dest) < 5 or dest.startswith('0000'):
			pln += (math.ceil(call.duration/60.0))
		elif dest.startswith('0000'):
			pln += (math.ceil(call.duration/60.0))
		elif '@' in dest:
			pln += (math.ceil(call.duration/60.0))
		elif call.rate == 0:
			free += (math.ceil(call.duration/60.0))
		else:
			cost += (math.ceil(call.duration/60.0))
	return int(cost), int(free), int(pln)

    def sum_charges(self, charges):
	credit = 0
	transfer = 0
	btc = 0
	for charge in charges:
                if float(charge.credit) < 0.0 and charge.concept:
		    transfer -= float(charge.credit)
                if charge.concept and 'btc @' in charge.concept:
		    btc += float(charge.credit)
                else:
		    credit += float(charge.credit)
	return [float(credit), transfer, btc]

    def minutes_stats(self, request, period, columns, val_checker, obj_class):
	model = Model()
	ts_start = time.time() - period
	ts_end = time.time()
	data = []
	current = 0
	for a in range(columns):
		selected = model.query(obj_class).filter(and_(obj_class.timestamp>datetime.fromtimestamp(ts_start), obj_class.timestamp<datetime.fromtimestamp(ts_end)))
		pars = list(val_checker(selected))
		data.insert(0, [pars, {'label': str(current)}])
		ts_start -= period
		ts_end -= period
		current -= 1
	return json.dumps(data)

    def general_stats(self):
	res = ""
	total = 0
	total_free = 0
	free_calls = 0
	cost_calls = 0
	total_cost = Decimal()
	total_benefit = Decimal()
	model = Model()
	calls = model.query(Call)
	for call in calls:
		cost = Decimal(call.cost)
		duration = call.charged
		minutes = duration/60
		if cost:
			total += duration
			cost_calls += 1
			total_cost += cost
			total_benefit += Decimal(minutes)*Decimal(0.001) + Decimal(0.001)
		else:
			total_free += duration
			free_calls += 1
        model = Model()
        btc_received = model.query(func.sum(Wallet.received)).scalar()
        btc_unconfirmed = model.query(func.sum(Wallet.unconfirmed)).scalar()
        btc_accounted = model.query(func.sum(Wallet.accounted)).scalar()
        if btc_unconfirmed:
            unconfirmed = '(+%.3f)' % (float(btc_unconfirmed), )
        else:
            unconfirmed = ''
	res += "<p>Minutos con coste: %s</p>\n" % (total/60,)
	res += "<p>Minutos gratis: %s</p>\n" % (total_free/60,)
	res += "<p>Llamadas: %s Gratis: %s Con coste: %s</p>\n" % (calls.count(), free_calls, cost_calls)
	res += "<p>Coste total %.3f Beneficio %.3f</p>" % (total_cost, total_benefit)
        res += "<p>btc in: %.3f %s out: %.3f</p>\n" % (float(btc_received), unconfirmed, float(btc_accounted))
	return res


if __name__ == '__main__':
	stats = StatsResource()
	print "minutes"
	print stats.minutes_stats(None, 60*60*24, 10, stats.sum_minutes, Call)
	print "credit"
	print stats.minutes_stats(None, 60*60*24, 10, stats.sum_credit, Call)
	print "charges"
	print stats.minutes_stats(None, 60*60*24, 10, stats.sum_charges, Charge)
