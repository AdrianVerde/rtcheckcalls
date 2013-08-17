#! /usr/bin/python
import urllib
from collections import defaultdict
from twisted.internet import reactor
import pprint
import json

# https://billing.jxtalk.com/rates.php
# http://www.webhostingtalk.com/archive/index.php/t-761599.html

global winners
winners = {}

providers = {}
providers['freevoipdeal'] = "http://www.freevoipdeal.com/calling_rates/"
providers['voipbuster'] = "https://www.voipbuster.com/en/rates"
providers['12voip'] = "http://www.12voip.com/calling_rates"
providers['voipdiscount'] = "http://www.voipdiscount.com/rates"
providers['justvoip'] = "http://www.justvoip.com/rates"
providers['nonoh'] = "http://www.nonoh.net/calling_rates/"
providers['actonvoip']= "http://www.actionvoip.com/rates"
providers['calleasy']= "http://www.calleasy.com/calling_rates"
providers['dialnow']= "http://www.dialnow.com/en/sip_rates"
providers['easyvoip']= "http://www.easyvoip.com/rates"
providers['internetcalls']= "http://www.internetcalls.com/rates"
providers['intervoip']= "http://www.intervoip.com/rates"
providers['jumblo']= "http://www.jumblo.com/rates"
providers['justvoip']= "http://www.justvoip.com/rates"
providers['lowratevoip']= "http://www.lowratevoip.com/rates"
providers['netappel']= "http://www.netappel.fr/rates" #french
providers['sipdiscount']= "http://www.sipdiscount.com/rates"
providers['powervoip']= "http://www.powervoip.com/rates"
providers['poivy']= "https://www.poivy.com/rates"
providers['powervoip']= "http://www.powervoip.com/rates"
providers['rynga']= "http://www.rynga.com/rates"
providers['smartvoip']= "http://www.smartvoip.com/"
providers['smsdiscount']= "http://www.smsdiscount.com/en/rates"
providers['smslisto']= "http://www.smslisto.com/en/calling_rates"
providers['voipcheap-uk']= "http://www.voipcheap.co.uk/rates"
providers['voipcheap']= "http://www.voipcheap.com/rates"
providers['voipbusterpro']= "http://www.voipbusterpro.com/rates"
providers['voipgain']= "http://www.voipgain.com/rates"
providers['voipraider']= "http://www.voipraider.com/en/rates"
providers['stuntcalls']= "http://www.stuntcalls.com/rates"
#providers['bestvoipreselling']= "https://www.bestvoipreselling.com/rates"
providers['voipstunt']= "http://www.voipstunt.com/en/calling_rates"
providers['voipwise']= "http://www.voipwise.com/rates"
providers['voipzoom']="http://www.voipzoom.com/calling_rates"
providers['webcalldirect']="http://www.webcalldirect.com/rates"
providers['cheapvoip']="http://www.cheapvoip.com/rates"
providers['freecall']="http://www.freecall.com/rates"
providers['powervoip']="http://www.powervoip.com/calling-rates.html"
providers['hotvoip']="http://www.hotvoip.com/rates"
#providers['voipyo']="http://voipyo.com/rates" # has no sip...
providers['terrassip']="http://www.terrasip.com/index.php?seite=tarife4&t_country=gb&language=gb&t_lang=en"
providers['budgetvoip']="http://www.budgetvoip.com/en/rates/"
codes = {}

def parse_codes():
	global codes
	f = open('data/countries.data')
	data = f.readlines()
	f.close()
	for line in data:
		parts = line.split(":")
		type = None
		if len(parts) > 1:
			name = parts[0].strip()
			code = parts[1].strip()
			if "-" in code:
				parts = code.split("-")
				code = parts[0]
				type = parts[1]
			codes[name.lower()] = [code, type]
	return codes
	
parse_codes()

def find_country_info(data, pos):
	pos2 = data.find('&nbsp;', pos)

	country = data[pos+(len('<td class="column-country">')):pos2]
	country = country.replace("&nbsp;", "").lower()
	type = None
	if country in codes:
		country, type = codes[country]
	else:
		print "No code for", country
		country = country

	pos3 = data.find('<span class="type">', pos)
	pos4 = data.find('</span>', pos3)

	if not type:
		type = data[pos3+len('<span class="type">'):pos4].strip("()").strip().lower()
		if type in codes:
			type, _ = codes[type]
		else:
			print "No code for", type
			country = type

	pos5 = data.find('<td class="column-vat">', pos)
	pos6 = data.find('</td>', pos5)

	rate = data[pos5+len('<td class="column-vat">'):pos6].strip(" $")
	return country, type, rate

def check_provider(rates_url):
	handle = urllib.urlopen(rates_url)
	data = handle.read()
	data = data.replace('trodd"><td>&nbsp;&nbsp;', 'trodd"><td class="column-country">')
	data = data.replace('treven"><td>&nbsp;&nbsp;', 'trodd"><td class="column-country">')
	data = data.replace(' [fixed] ', '&nbsp;<span class="type">(Landline)</span>&nbsp;')
	data = data.replace(' [mobile] ', '&nbsp;<span class="type">(Mobile)</span>&nbsp;')
	data = data.replace('ratesvat', 'column-vat')
	pos = data.find('<td class="column-country">')

	rates = defaultdict(dict)
	while(pos>0):
	    country, type, rate = find_country_info(data, pos)
	    pos = data.find('<td class="column-country">', pos+1)
	    rates[country][type] = rate

	return rates

def get_saved_winners():
	global winners
	f = open('data/winners.json')
	data = f.read()
	f.close()
	try:
		winners = json.loads(data)
	except:
		# probably daemon writing, will check later..
		pass
	return winners

def get_winners(daemon=False):
	global winners
	seen_countries = set()
	if not daemon:
		# running in rtcheckcalls, return saved winners from daemon
		return get_saved_winners()
	rates = {}
	for provider in providers:
		try:
			rates[provider] = check_provider(providers[provider])
			f = open('data/providers/' + provider + '.json', 'w')
			f.write(json.dumps(rates[provider]))
			f.close()
		except:
			print "error on", provider

	winners = {}

	for provider in rates:
	    for country in rates[provider]:
		for type in rates[provider][country]:
		    rate = str(rates[provider][country][type].strip())
                    if rate == 'free-':
                        rate = "FREE*"
		    key = str(country)+" "+str(type)
		    if not key in winners:
			winners[key] = [rate, [provider]]
		    else:
			champion = winners[key]
			champion_rate = champion[0]
			if champion_rate == rate:
			      champion[1].append(provider)
			elif champion_rate == "FREE*":
			      pass
			elif rate == "FREE*":
			      champion[0] = "FREE*"
			      champion[1] = [provider]
			else:
				rate = float(rate)
				champion_rate = float(champion_rate)
				if rate < champion_rate:
					champion[0] = rate
					champion[1] = [provider]

	return winners

def save_winners():
	print "checking"
	winners = get_winners(True)
	f = open('data/winners.json', 'w')
	f.write(json.dumps(winners))
	f.close()
	reactor.callLater(600, save_winners)
	print "saving"

def load_provider(name):
	try:
		f = open('data/providers/' + name + '.json')
	except:
		return {}
	data = f.read()
	f.close()
	return json.loads(data)


if __name__ == '__main__':
	reactor.callLater(1, save_winners)
	reactor.run()

