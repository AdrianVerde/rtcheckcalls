from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()

from sqlalchemy import Column, Integer, String, Sequence, Numeric, DateTime, Float, ForeignKey, Text, Boolean

from sqlalchemy.orm import sessionmaker, relationship, backref, scoped_session
from datetime import datetime
import time

from decimal import Decimal

from obelisk.config import config

from wallet import get_address

class User(Base):
	__tablename__ = 'users'
	id = Column(Integer, Sequence('user_id_seq'), primary_key=True)
	voip_id = Column(String(50))
	credit = Column(Numeric(10,6), default=0.0)
	admin = Column(Boolean, default=False)
	name = Column(String(50))
	email = Column(String(128))
	email_validated = Column(Boolean, default=False)

        def get_address(self):
            # get receiving btc address
            return get_address(self.id)

        def update_wallet(self, model):
            # create the wallet if needed
            if not len(self.wallets):
                wallet = Wallet(self)
                model.session.add(wallet)
                model.session.commit()

	def __init__(self, voip_id):
		self.voip_id = voip_id
		self.credit = Decimal()
		self.admin = 0
	def __repr__(self):
		return "<User('%s', '%s')>" % (self.voip_id, self.credit)

class Provider(Base):
	__tablename__ = 'providers'
	id = Column(Integer, Sequence('provider_id_seq'), primary_key=True)
	name = Column(String(50))
	def __init__(self, name):
		self.name = name

class Call(Base):
	__tablename__ = 'calls'
	id = Column(Integer, Sequence('call_id_seq'), primary_key=True)
	user_id = Column(ForeignKey('users.id'))
	user = relationship("User", backref=backref('calls', order_by=id))

	destination = Column(String(50))
	timestamp = Column(DateTime())
	duration = Column(Integer())
	charged = Column(Integer())
	cost = Column(Numeric(10,6))
	rate = Column(Numeric(10,6))
	provider_id = Column(ForeignKey('providers.id'))
	provider = relationship("Provider", backref=backref('calls', order_by=id, lazy='dynamic'))
	def __repr__(self):
		return "<Call('%s','%s', '%s')>" % (self.destination, self.timestamp, self.duration)

class Charge(Base):
	__tablename__ = 'charges'
	id = Column(Integer, Sequence('charge_id_seq'), primary_key=True)
	user_id = Column(ForeignKey('users.id'))
	user = relationship("User", backref=backref('charges', order_by=id))
	initiator_id = Column(Integer) # TODO add foreign key
        funded = Column(Boolean, default=False)
	#initiator = relationship("User", backref=backref('charged', order_by=id))

	timestamp = Column(DateTime())
	credit = Column(Numeric(10,6))
	concept = Column(Text())
	def __repr__(self):
		return "<Charge('%s','%s', '%s')>" % (self.user, self.timestamp, self.credit)

class WebSession(Base):
	__tablename__ = 'sessions'
	id = Column(Integer, Sequence('session_id_seq'), primary_key=True)
	session_id = Column(String(40))
	timestamp = Column(DateTime())
	user_id = Column(ForeignKey('users.id'))
	user = relationship("User", backref=backref('sessions', order_by=id))

class Wallet(Base):
    __tablename__ = 'wallets'
    id = Column(Integer, Sequence('wallet_id_seq'), primary_key=True)
    address = Column(String(128))
    received = Column(Numeric(16, 8))
    unconfirmed = Column(Numeric(16, 8))
    accounted = Column(Numeric(16, 8))

    # linked accounts
    user_id = Column(ForeignKey('users.id'))
    user = relationship("User", backref=backref('wallets', order_by=id))

    def __init__(self, user):
        self.user = user
        self.address = get_address(user.id)
        self.received = Decimal("0")
        self.unconfirmed = Decimal("0")
        self.accounted = Decimal("0")

    def get_address(self):
        return get_address(self.user.id)


# only one per application for thread-local storage
# http://docs.sqlalchemy.org/en/latest/orm/session.html#unitofwork-contextual
cfg = config['db']
user = cfg['user']
password = cfg['password']
host = cfg.get('host', 'localhost')
database = cfg['database']
engine =create_engine('mysql://%s:%s@%s/%s' % (user, password, host, database), pool_size=15)
for a in [User, Call, Charge, WebSession]:
	a.__table__.mysql_engine='InnoDB'
	a.__table__.mysql_charset='utf8'

Base.metadata.create_all(engine)

session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)

# Another thing to be aware of us the pool_size of the connection pool, which is 5 by default. For many applications that's fine, but if you are creating lots of threads, you might need to tune that parameter
# http://stackoverflow.com/questions/9619789/sqlalchemy-proper-session-handling-in-multi-thread-applications

class Model(object):
	def __init__(self):
		#engine.execute("CREATE DATABASE alchemy")
		#engine.execute("USE dbname")
		#engine =create_engine('sqlite:///:memory:', echo=False)
		#Session.configure(bind=self._engine)  # once engine is available
		self.session = Session()
	def query(self, *args, **kargs):
		return self.session.query(*args, **kargs)
	def get_user(self, session_id):
		web_session = self.session.query(WebSession).filter_by(session_id=session_id).first()
		if web_session:
			return web_session.user
		else:
			return None
	def get_user_fromext(self, user_ext):
		user = self.query(User).filter_by(voip_id=user_ext).first()
		return user
	def create_test_data(self):
		ed_user = User('815')
		call = Call(user=ed_user, destination='815', timestamp=datetime.now(), duration=6, cost=8.4, rate=0.005)
		charge = Charge(user=ed_user, timestamp=datetime.fromtimestamp(time.time()), credit=10.0)
		web_session = WebSession(session_id='session_1', timestamp=datetime.now(), user=ed_user)
		self.session.add(ed_user)
		self.session.add(call)
		self.session.add(charge)
		self.session.add(web_session)
		self.session.commit()
		self.session.add_all([
		     User('wendy'),
		     User('mary'),
		     User('fred')])

		#print self.session.dirty
		#print self.session.new

		self.session.commit()



if __name__ == "__main__":
	model = Model()

	our_user = model.query(User).filter_by(voip_id='815').first()

	print "search ", our_user

	#print ed_user is our_user

	print "CALLS",our_user.calls
	print "CHARGES",our_user.charges

	print model.get_user('session_1')
	print model.get_user('session_2')


