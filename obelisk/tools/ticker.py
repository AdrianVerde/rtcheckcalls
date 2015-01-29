import json
import urllib2
from twisted.internet import reactor
from twisted.python import log

from twisted.web.client import getPage

import traceback
import random

price = 420.0
mins = 30

# RIP :)
#def from_mtgox():
#    d = getPage('http://data.mtgox.com/api/1/BTCEUR/ticker')
#    return d

def from_btcavg():
    d = getPage('https://api.bitcoinaverage.com/ticker/global/EUR/')
    return d

def parse_results(data):
    if data.get('ask'):
        return float(data['ask'])

def wait_and_tick(err=None):
   reactor.callLater(60*mins+random.randint(0, 60*mins), ticker)
     
def ticker_update(data):
    global price
    data = json.loads(data)
    price = parse_results(data)

def error_connecting(failure):
    print failure
    log.err("Problems on ticker " + str(failure.printTraceback()), system='Ticker,mtgox')
    wait_and_tick

def ticker():
    global price
    try:
        d = from_btcavg()
        d.addCallback(ticker_update)
        d.addCallback(wait_and_tick)
        d.addErrback(error_connecting)
    except:
        # call each 
        log.err("Problems on ticker", system='Ticker,mtgox')
        log.err(traceback.format_exc(), system='Ticker,mtgox')
        wait_and_tick()

if __name__ == '__main__':
    ticker()
    reactor.run()

