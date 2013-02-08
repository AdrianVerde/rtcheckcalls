from twisted.internet import reactor
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

def notify_sse(text, section='rtcheckcalls', user=None):
	if sse.resource:
		try:
			sse.resource.notify(text, section, user)
		except:
			print traceback.print_exc()

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
	    print text
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
            self._provider = provider
	    self.log("call from %s to %s with %s mana remaining (%s)" % (self._from, self._real_to, accounting.get_mana(self._from_exten), self._provider))
    def on_answer(self, args):
	    # XXX avoid multiple answers...
	    if not args['calleridani']:
		    # no from
		    return
	    if args['exten'] in ['s-CONGESTION',  's-BUSY', 's-CHANUNAVAIL', 's-NOANSWER']: # 6
                return False
	    self.log("check %s answered %s on channel %s" % (args['calleridani'], args['calleriddnid'], args['channel']))
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
		    self.log("%s answered on channel %s" % (self._from, channel))
		    self._starttime = parse_time(args['eventtime'])
		    self._channel = channel
		    self.predict_cut()
		    #reactor.callLater(10, self.cut_call, channel)
    def predict_cut(self):
	    if not self._cost:
		    if self._provider == 'ovh':
			time_to_cut = ((59 - random.randint(0,4))*60.0)-random.randint(0,30)
		        self.log("ovh call, CUT IN %sm" %(time_to_cut/60.0))
		        self._callID = reactor.callLater(int(time_to_cut), self.cut_call, self._channel, "time limit reached on provider")
			return
		    self.log("free call, will not be cut")
		    return
	    mana = accounting.get_mana(self._from_exten)
	    if not mana or mana < 0.0:
		    self.cut_call(self._channel, "not enough credit for call")
	    else:
		    time_to_cut = (float(mana) / float(self._cost)) * 60.0
		    self.log("CUT IN %sm" %(time_to_cut/60.0))
		    self._callID = reactor.callLater(int(time_to_cut), self.cut_call, self._channel, "out of credit while calling")
    def cut_call(self, channel, reason=""):
	    self._callID = 0
	    if reason:
		    self.log("CUTTING CALL (%s)" % (reason, ))
	    else:
		    self.log("CUTTING CALL")
            print cli.run_command("channel request hangup %s" % (channel))
    def on_chan_start(self, args):
	    channel = args['channel']
	    # precut call if user can't pay it
	    mana = float(accounting.get_mana(self._from_exten))
	    if self._cost and (not mana or mana < self._cost):
		    self.cut_call(channel, "not enough credit")
    def on_hangup(self, args):
	    if self._callID:
		    self._callID.cancel()
		    self._callID = 0
	    # convert time
	    endtime = parse_time(args['eventtime'])
	    if self._starttime:
	    	    totaltime = endtime - self._starttime
		    self.apply_costs(totaltime)
		    self.log("call end %.1f seconds at %s per minute" % (totaltime, self._cost))
            else:
		    self.log("unsuccesfull call")

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
                    calls.add_call(self._from_exten, self._real_to, self._starttime, totaltime, roundedtime, totalcost, self._cost, self._provider)

class CallManager(object):
    def __init__(self):
	self._commands = {}
	self._commands["HANGUP"] = self.on_hangup
	self._commands["CHAN_START"] = self.on_chan_start
	self._commands["APP_START"] = self.on_app_start
	self._commands["CHAN_END"] = self.on_chan_end
	self._commands["ANSWER"] = self.on_answer
	#self._commands["BRIDGE_START"] = self.on_bridge_start
	#self._commands["BRIDGE_END"] = self.on_bridge_end
	self._calls = {}

    def write(self, text):
	print text
	pass

    def on_event(self, event):
	command = event['eventname']
	if command in self._commands:
            try:
	        res = self._commands[command](event)
	    except:
		print "ERROR on event", event
		traceback.print_exc()
	else:
	    self.write("? " + command + " " + str(event))

    def on_chan_start(self, args):
	    app_uniqid = args['linkedid']
	    if app_uniqid in self._calls:
		    self._calls[app_uniqid].on_chan_start(args)
	    self.write("chan start: " +  str(args) + " " + str(args['uniqueid']))

    def on_app_start(self, args):
	    app_from = args['calleridani'] # 3
	    app_to = args['calleriddnid'] # 5
	    if not app_to:
		provider = args['appdata'] # 10
		parts = provider.split("/")
		if len(parts) > 2:
			app_to = parts[2].split(",")[0]
	    app_uniqid = args['linkedid']
	    app_cost = args['accountcode']
	    self.write("app start: " + app_from + " " + app_to + " " + str(args['linkedid']) + " " + str(args))
	    if not app_uniqid in self._calls:
		    self._calls[app_uniqid] = CallMonitor(app_uniqid, app_cost, app_from, app_to)
		    self._calls[app_uniqid].on_app_start(args)

    def on_chan_end(self, args):
	    self.write("chan end: " +  str(args) + " " + str(args['uniqueid']))

    def on_hangup(self, args):
	    #print "HANGUP", args
	    if not args['calleridani']:
		return
	    app_uniqid = args['uniqueid']
	    if app_uniqid in self._calls:
		    self._calls[app_uniqid].on_hangup(args)
		    del self._calls[app_uniqid]
	    self.write("hangup: " + " " + str(args) + " " + str(args['uniqueid']))

    def on_answer(self, args):
	    app_uniqid = args['linkedid']
	    if app_uniqid in self._calls:
		    res = self._calls[app_uniqid].on_answer(args)
		    if res == False:
			print "deleting from congestion"
			del self._calls[app_uniqid]
	    self.write("answer: " + str(args) + " " + args['uniqueid'])

if __name__ == '__main__':
	from tail import tail
	from time import sleep
	m = CallManager()
	
	m.on_text('"HANGUP","1354410942.161893","","701","","","","","from-payuser","SIP/1.0.0.9-00000001","AppDial","(Outgoing Line)","3","0.0","1354410928.1","1354410928.0","","","","16,SIP/1.0.0.9-00000001,"')
	
	t = tail(filename, m.on_text)
	while True:
		t.process()
		sleep(1)


