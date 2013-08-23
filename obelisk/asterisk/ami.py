from twisted.internet import reactor
from twisted.python import log
from starpy import manager
from collections import defaultdict
import base64
import logging

global connector
connector = None

from obelisk.asterisk.users import reload_peers

def connect():
	global connector
	connector = AMIConnector()

class PersistentAMIProtocol(manager.AMIProtocol):
	def connectionLost( self, reason ):
		global connector
		log.err("disconnected wait 5 seconds to connect %s" % (reason,), system='AMI')
		reactor.callLater(5, connector.connect)
		return manager.AMIProtocol.connectionLost(self, reason)

manager.AMIFactory.protocol = PersistentAMIProtocol

class AMIConnector(object):
	def __init__(self):
		self._shutdown = False
		self.connect()
		self._callbacks = defaultdict(list)

        def log(self, text):
                log.msg(str(text), sytem='AMI')

	def registerEvent(self, event, cb):
		self._callbacks[event].append(cb)

	def runCallbacks(self, ami, event):
		for cb in self._callbacks[event['event']]:
			cb(event)

	def connect(self):
		from obelisk.config import config
		self.connected = True
		self._f = manager.AMIFactory(config['ami']['user'], config['ami']['password'])
		#logging.basicConfig()
		#manager.log.setLevel( logging.DEBUG )
		host = config['ami'].get('host', 'localhost')
		port = config['ami'].get('port', 5038)
		df = self._f.login(host, port)
		df.addCallback(self.onLogin)
		df.addErrback(self.onLoginError)

	def onLoginError(self, *args):
		log.err("Login problem, wait 10 seconds to connect", system='AMI')
		reactor.callLater(10, self.connect)

	def resetCalls(self):
		from obelisk import rtcheckcalls
		self.log("Doing a hard reset")
		rtcheckcalls.manager.reset_calls()

	def onLogin(self, ami):
		if self._shutdown:
			self.resetCalls()
                self._shutdown = False
		self.ami = ami
		"""
		self.ami.registerEvent( 'Hangup', self.onChannelHangup)
		self.ami.registerEvent( 'Dial', self.onDial)
		self.ami.registerEvent( 'Newchannel', self.onNewChannel)
		self.ami.registerEvent( 'Pickup', self.onPickup)
		self.ami.registerEvent( 'ExtensionStatus', self.onPeerStatus)
		self.ami.registerEvent( 'ChannelReload', self.onReload)
		"""
		self.ami.registerEvent('Shutdown', self.onShutdown)
		#self.ami.registerEvent('FullyBooted', self.onFullyBooted)
		self.ami.registerEvent('CEL', self.runCallbacks)
		self.ami.registerEvent('PeerStatus', self.runCallbacks)
		self.ami.registerEvent('Reload', self.onReload)
		self.ami.registerEvent('VarSet', self.onVarSet)
		self.log("Login ok")
		reload_peers()

	def onFullyBooted(self, ami, event):
		print 'FullyBooted',event
		#self.sendMessage('"admin" <sip:admin@pbx.lorea.org>', 'sip:caedes_roam', 'all systems functional')
		#self.sendAction('MailboxStatus', mailbox='6001')
		#self.sendAction('MailboxCount', mailbox='6001')
		#self.sendAction('SIPshowregistry')
		#self.sendAction('SIPshowpeer', peer='caedes')
		#self.sendAction('SIPpeerstatus')

	def onDial(self, ami, event):
		print 'dial',event

	def onPeerStatus(self, ami, event):
		print 'peerstate', event

	def onVarSet(self, ami, event):
                if event.get('variable','') == 'puertorico-fixmob-provider':
                        self.onReload(ami, event)

	def onReload(self, ami, event):
		self.log('Reload (%s)' % (event.get('event', 'Unknown'),))
		reload_peers()

	def onShutdown(self, ami, event):
		self._shutdown = True
		self.log('Shutdown %s' % (str(event),))

	def onChannelHangup(self, ami, event):
		print 'channel hangup',event

	def onNewChannel(self, ami, event):
		print 'newchannel',event

	def onPickup(self, ami, event):
		print 'pickup',event

	def messageSent(self, result):
		print "message sent", result

	def messageError(self, *args):
		print "message error", args[0], 'ok'
		return True

	def sendMessage(self, from_user, to_user, text, cb=None, eb=None):
        	self.sendAction('MessageSend', {'action':'MessageSend','from':from_user,'to':to_user ,'base64body': base64.b64encode(text)})

	def actionCallback(self, *args):
		print "callback", args

	def sendAction(self, action, pars={}, cb=None, eb=None, **kwargs):
        	message = {'action': action}
		message.update(pars)
		message.update(kwargs)
 	        #defer = self.ami.sendDeferred( message ).addCallback( self.actionCallback ).addErrback(self.actionCallback)
 	        #defer = self.ami.sendDeferred( message ).addCallback( self.ami.errorUnlessResponse )
 	        defer = self.ami.sendDeferred( message )
		#defer.addCallback(self.messageSent).addErrback(self.messageError)
		if cb:
			defer.addCallback(cb)
		if eb:
			defer.addCallback(eb)


if __name__ == '__main__':
	manager.log.setLevel( logging.DEBUG )
	logging.basicConfig()

	connect()
	reactor.run()
