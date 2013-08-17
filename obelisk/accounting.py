from twisted.internet import reactor
import os
from decimal import Decimal

from obelisk import charges
from obelisk.model import Model, User
from obelisk.asterisk.model import SipPeer
from obelisk.asterisk.users import reload_peer

class Accounting(object):
	def __init__(self):
		self.model = Model()

	def get_data(self):
		data = {}
		users = self.model.query(User)
		for user in users:
			if user.credit:
				data[user.voip_id] = user.credit
		return data

	def get_credit(self, user_ext):
		user = self.model.get_user_fromext(user_ext)
		if user:
			return user.credit
		else:
			return Decimal()

	def reset_credit(self, user_ext):
		user = self.model.get_user_fromext(user_ext)
		user.credit = Decimal()
		self.model.session.commit()
		self.update_user_context(user)

	def update_user_context(self, user):
		peer = self.model.query(SipPeer).filter_by(regexten=user.voip_id).first()
		if not peer:
			# old user
			print "user unavailable to update context", user.voip_id
			return
		if user.credit > Decimal(0.0) and peer.context == "from-freeuser":
			peer.context = "from-payuser"
			self.model.session.commit()
			reload_peer(peer.name)
		elif user.credit <= Decimal(0.0) and peer.context == "from-payuser":
			peer.context = "from-freeuser"
			self.model.session.commit()
			reload_peer(peer.name)

	def get_user_for_credit(self, user_ext):
		user = self.model.get_user_fromext(user_ext)
		if not user:
			# check at least user exists as asterisk user
			peer = self.model.query(SipPeer).filter_by(regexten=user_ext).first()
			if not peer:
				# check by name
				peer = self.model.query(SipPeer).filter_by(name=user_ext).first()
				if not peer:
					return
				else:
					user =  self.model.get_user_fromext(peer.regexten)
			if not user:
				user = User(peer.regexten)
				self.model.session.add(user)
		return user
	
	def transfer_credit(self, logged, user_ext, credit):
		from obelisk.resources import sse
		if not (credit > 0.0 and logged.credit >= credit):
			return
		user = self.get_user_for_credit(user_ext)
		if not user:
			return
		logged.credit -= Decimal(credit)
		user.credit += Decimal(credit)
		self.model.session.commit()
		self.update_user_context(user)
		self.update_user_context(logged)
		charges.add_charge(logged, user.voip_id, credit, 'transferencia de ' + logged.voip_id)
		charges.add_charge(logged, logged.voip_id, -credit, 'transferencia a ' + user.voip_id)
		sse.resource.notify({'credit': float(user.credit), 'user': user.voip_id}, "credit", user)
		sse.resource.notify({'credit': float(logged.credit), 'user': logged.voip_id}, "credit", logged)
	
	def add_credit(self, logged, user_ext, credit, reason=""):
		from obelisk.resources import sse
		user = self.get_user_for_credit(user_ext)
		if not user:
			return
		user.credit += Decimal(credit)
		self.model.session.commit()
		self.update_user_context(user)
		charges.add_charge(logged, user.voip_id, credit, reason)
		sse.resource.notify({'credit':float(user.credit), 'user':user.voip_id}, "credit", user)
		return user.voip_id

	def remove_credit(self, user_ext, credit):
		user = self.model.get_user_fromext(user_ext)
		if not user:
			return

		user.credit -= Decimal(credit)
		self.model.session.commit()
		self.update_user_context(user)

accounting = Accounting()

if __name__ == '__main__':
	print accounting.get_data()
	print accounting.get_credit('816')
	accounting.reset_credit('816')
	accounting.add_credit('816', 1.949000)
	print accounting.get_credit('816')
	accounting.remove_credit('816', 1.0)
	print accounting.get_credit('816')
