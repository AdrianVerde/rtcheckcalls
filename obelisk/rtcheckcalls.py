from twisted.internet import reactor
from twisted.python import log
from decimal import Decimal
import math
import traceback
import random
import time

def parse_time(formatted_time):
	return time.mktime(time.strptime(formatted_time, "%Y-%m-%d %H:%M:%S"))

from obelisk.accounting import accounting
from obelisk.resources import sse
from obelisk import calls
from obelisk.model import Model, User
from obelisk.asterisk.model import SipPeer
from obelisk.asterisk import cli

filename = "/var/log/asterisk/cel-custom/Master.csv"

manager = None

def notify_sse(text, section='rtcheckcalls', user=None):
	if sse.resource:
		try:
			sse.resource.notify(text, section, user)
		except:
			log.err(traceback.format_exc(), system='Billing')

class CallMonitor(object):
    def __init__(self, id, cost, app_from, app_to):
	    self._id = id
	    self._callID = 0
            self._provider = 'unknown'
            if cost:
		    self._realcost = Decimal(cost)
	    else:
		    self._realcost = Decimal()
	    try:
		    self._cost = Decimal(cost)
		    if self._cost:
			    self._cost += Decimal(0.001) # benefit margin
	    except:
		    self._cost = Decimal(0.0)
	    self._from = app_from
	    self._to = app_to
	    self._real_to = app_to
	    model = Model()
	    peer = model.query(SipPeer).filter_by(regexten=self._from).first()
	    if peer:
		self._from = peer.name
		self._user = model.query(User).filter_by(voip_id=peer.regexten).first()
		self._from_exten = peer.regexten
	    else:
		self._user = None
		self._from_exten = ''
    def log(self, text):
	    notify_sse(text, 'callmonitor', self._user)
            log.msg(text, system='Billing,'+str(self._id))
    def on_app_start(self, event):
	    self._starttime = 0
            provider = event['appdata'].split("/")
	    if len(provider) > 2:
		provider = provider[1]
	    elif "@" in provider[1]:
		dest = provider[1].split(",")[0]
		provider = 'sip'
		self._real_to = dest
	    else:
		provider = 'direct'
	    if not self._real_to:
		# incoming calls from other providers
		self._real_to = event['exten']
	    notify_sse({'cost': float(self._cost), 'from': self._from, 'to': self._real_to, 'event': 'start'}, 'call_monitor', self._user)
            self._provider = provider
	    self.log("Call from %s to %s with %.3f mana remaining (%s)" % (self._from, self._real_to, accounting.get_credit(self._from_exten), self._provider))
    def on_answer(self, args):
	    # XXX avoid multiple answers...
	    if not args['calleridani']:
		    # no from
		    return
	    if args['exten'] in ['s-CONGESTION',  's-BUSY', 's-CHANUNAVAIL', 's-NOANSWER']: # 6
                return False
	    #self.log("check %s answered %s on channel %s" % (args['calleridani'], args['calleriddnid'], args['channel']))
	    answer_to = args['calleriddnid']
	    if not answer_to and self._from_exten == args['calleridani']:
		provider = args['appdata']
		parts = provider.split("/")
		answer_to = parts[2].split(",")[0]
	    if self._from_exten == args['calleridani'] and answer_to in self._to:
		    if self._starttime:
			# already answered
			return
		    channel = args['channel']
		    self.log("%s answered on channel %s" % (self._from, channel.split('@')[0]))
	    	    notify_sse({'from': self._from, 'to': self._real_to, 'event': 'answer'}, 'call_monitor', self._user)
		    self._starttime = parse_time(args['eventtime'])
		    self._our_starttime = time.time()
		    self._channel = channel
		    self.predict_cut()
		    #reactor.callLater(10, self.cut_call, channel)
    def predict_cut(self):
	    if not self._cost:
		    if self._provider == 'ovh' or self._provider == 'ovh2':
			time_to_cut = ((59 - random.randint(0,4))*60.0)-random.randint(0,30)
		        self.log("Ovh call, CUT IN %sm" %(time_to_cut/60.0))
		        self._callID = reactor.callLater(int(time_to_cut), self.cut_call, self._channel, "time limit reached on provider")
			return
		    self.log("Free call, will not be cut")
		    return
	    mana = accounting.get_credit(self._from_exten)
	    if not mana or mana < 0.0:
		    self.cut_call(self._channel, "not enough credit for call")
	    else:
		    time_to_cut = (float(mana) / float(self._cost)) * 60.0
		    self.log("Cut in %sm" %(time_to_cut/60.0))
		    self._callID = reactor.callLater(int(time_to_cut), self.cut_call, self._channel, "out of credit while calling")
    def cut_call(self, channel, reason=""):
	    self._callID = 0
	    if reason:
		    self.log("CUTTING CALL (%s)" % (reason, ))
	    else:
		    self.log("CUTTING CALL")
            res = cli.run_command("Channel request hangup %s" % (channel))
    	    self.log(str(res))
    def on_chan_start(self, args):
	    channel = args['channel']
	    # precut call if user can't pay it
	    mana = float(accounting.get_credit(self._from_exten))
	    if self._cost and (not mana or mana < self._cost):
		    self.cut_call(channel, "not enough credit")
    def on_hangup(self, args={}):
	    if self._callID:
		    self._callID.cancel()
		    self._callID = 0
	    # convert time
	    if args.get('eventtime', False):
		    endtime = parse_time(args['eventtime'])
            else:
		    # finish by request
		    starttime = self._our_starttime
		    endtime = date.time()
                    endtime = self._starttime + (endtime - starttime)
	    if self._starttime:
	    	    totaltime = endtime - self._starttime
		    self.apply_costs(totaltime)
		    self.log("Call end %.1f seconds at %.3f per minute" % (totaltime, self._cost))
            else:
		    self.log("Unsuccesfull call")
	    	    notify_sse({'from': self._from, 'to': self._real_to, 'event': 'hangup', 'cost': 0}, 'call_monitor', self._user)

    def apply_costs(self, totaltime):
	    if self._from_exten:
		    # round up to closest second
		    totaltime = math.ceil(totaltime)
		    # round up to closest minute
		    roundedtime = totaltime
		    if totaltime % 60:
			    roundedtime += 60 - (totaltime % 60)
	            minutes = roundedtime / 60
	            # calculate total cost
		    totalcost = self._cost * Decimal(minutes)
		    # add call establishment
		    if self._cost:
			    totalcost += Decimal('0.001')
		            # save accounting data
		    	    accounting.remove_credit(self._from_exten, totalcost)
	    	    notify_sse({'from': self._from, 'to': self._real_to, 'event': 'hangup', 'cost': float(totalcost), 'duration': totaltime, 'charged': roundedtime}, 'call_monitor', self._user)
                    calls.add_call(self._from_exten, self._real_to, self._starttime, totaltime, roundedtime, totalcost, self._cost, self._provider)

class CallManager(object):
    def __init__(self):
        global manager
        manager = self
	self._commands = {}
	self._commands["HANGUP"] = self.on_hangup
	self._commands["CHAN_START"] = self.on_chan_start
	self._commands["APP_START"] = self.on_app_start
	self._commands["CHAN_END"] = self.on_chan_end
	self._commands["ANSWER"] = self.on_answer
	#self._commands["BRIDGE_START"] = self.on_bridge_start
	#self._commands["BRIDGE_END"] = self.on_bridge_end
	self._calls = {}

    def log(self, text):
        log.msg(text, system='Billing,manager')

    def on_event(self, event):
	command = event['eventname']
	if command in self._commands:
            try:
	        res = self._commands[command](event)
	    except:
        	log.err("Error on event " + str(event), system='Billing')
		log.err(traceback.format_exc(), system='Billing')
	elif not command in ['BRIDGE_START', 'BRIDGE_END']:
	    self.log("? " + command + " " + str(event))

    def on_chan_start(self, args):
	    app_uniqid = args['linkedid']
	    if app_uniqid in self._calls:
		    self._calls[app_uniqid].on_chan_start(args)
	    #self.log("chan start: " +  str(args) + " " + str(args['uniqueid']))

    def on_app_start(self, args):
	    app_from = args['calleridani'] # 3
            if not app_from:
	        app_from = args['calleridnum'] # 3
	    app_to = args['calleriddnid'] # 5
	    if not app_to:
		provider = args['appdata'] # 10
		parts = provider.split("/")
		if len(parts) > 2:
			app_to = parts[2].split(",")[0]
	    app_uniqid = args['linkedid']
	    app_cost = args['accountcode']
	    #self.log("app start: " + app_from + " " + app_to + " " + str(args['linkedid']) + " " + str(args))
	    if not app_uniqid in self._calls:
		    self._calls[app_uniqid] = CallMonitor(app_uniqid, app_cost, app_from, app_to)
		    self._calls[app_uniqid].on_app_start(args)

    def on_chan_end(self, args):
	    #self.log("chan end: " +  str(args) + " " + str(args['uniqueid']))
            pass

    def reset_calls(self):
	    self.log("reset all calls")
            keys = self._calls.keys()
	    for app_uniqid in keys:
                self._calls[app_uniqid].on_hangup()
                del self._calls[app_uniqid]
	        self.log("hangup: " + str(app_uniqid))

    def on_hangup(self, args):
	    #print "HANGUP", args
	    if not args['calleridani']:
		return
	    app_uniqid = args['uniqueid']
	    if app_uniqid in self._calls:
		    self._calls[app_uniqid].on_hangup(args)
		    del self._calls[app_uniqid]
	    #self.log("hangup: " + " " + str(args) + " " + str(args['uniqueid']))

    def on_answer(self, args):
	    app_uniqid = args['linkedid']
	    if app_uniqid in self._calls:
		    res = self._calls[app_uniqid].on_answer(args)
		    if res == False:
        		log.msg("Deleting from congestion: " + str(app_uniqid), system='Billing,manager')
			del self._calls[app_uniqid]
	    #self.log("answer: " + str(args) + " " + args['uniqueid'])

if __name__ == '__main__':
	from tail import tail
	from time import sleep
	m = CallManager()
	
	m.on_text('"HANGUP","1354410942.161893","","701","","","","","from-payuser","SIP/1.0.0.9-00000001","AppDial","(Outgoing Line)","3","0.0","1354410928.1","1354410928.0","","","","16,SIP/1.0.0.9-00000001,"')
	
	t = tail(filename, m.on_text)
	while True:
		t.process()
		sleep(1)


