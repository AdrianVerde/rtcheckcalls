from incf.countryutils import transformations
import traceback
from collections import defaultdict

from obelisk.asterisk.providers import get_providers
from obelisk.pricechecker import get_winners, load_provider
from obelisk.asterisk.prefixes import parse_prices

def normalize_price(price):
	if price == 'FREE*':
		price = 0.0
	return float(price)

def check_prices():
	output = ""
	prices = parse_prices()
	#provider_prices = load_provider(name)
	providers = get_providers()
	loaded_providers = {}
	winners = get_winners()
	better_deal = ""
	countries = prices.keys()
	countries.sort()
	counters = defaultdict(int)
	output += 'remember rs has no prices (new republic of serbia)\n'
	for country in countries:
		if country == 'rs':
			# we have a warning above... known problem XXX
			continue
		for type in prices[country]:
			current_rate, provider_code, ext = prices[country][type]
			if provider_code in providers:
				try:
					country_name = transformations.ccn_to_cn(transformations.cca2_to_ccn(country))
				except:
					country_name = 'Unknown'
				if provider_code in loaded_providers:
					provider_prices = loaded_providers[provider_code]
				else:
					names = providers[provider_code]
					if names.__class__ ==  str:
						names = [names]
					all_prices = []
					all_providers = set()
					for name in names:
						if name in ['kali', 'shiva', 'opum']:
							name = 'freevoipdeal'
						elif name[:-1] in ['freevoipdeal']:
							name = 'freevoipdeal'
						elif name[:-2] in ['freevoipdeal']:
							name = 'freevoipdeal'
						elif name[:-1] in ['budgetvoip']:
							name = 'budgetvoip'
						elif name[:-1] in ['hotvoip']:
							name = 'hotvoip'
						all_providers.add(name)
						# XXX check if prices are the same for given country...
						provider_prices = load_provider(name)
						loaded_providers[provider_code] = provider_prices
						try:
							country_price = normalize_price(provider_prices[country][type])
							all_prices.append(country_price)
						except:
							traceback.print_exc()
							output += "problem with %s %s %s %s\n" % (name, country, type, name)
					ok = True
					if all_prices:
						last_price = all_prices[0]
						for aprice in all_prices:
							if aprice != last_price:
								output += country_name + " ["+country+"]\t"+type +  " Price inconsistency %s %s\n" % (str(all_prices), str(all_providers))
								ok = False
					else:
						output += "No prices for %s %s %s %s\n" % (name, country, type, str(all_providers))
				if country in provider_prices and type in provider_prices[country]:
					current_rate = float(current_rate)
					names = providers[provider_code]
					provider_rate = normalize_price(provider_prices[country][type])
					if current_rate != provider_rate:
						key = country + " " + type
						if key in winners:
							output += country_name + " ["+country+"]\t"+type + " %s -> %s %s %s\n" % (str(current_rate), str(provider_rate), str(providers[provider_code]), str(winners[key]))
						else:
							output += country_name + " ["+country+"]\t"+type + " %s -> %s %s\n" % (str(current_rate), str(provider_rate), str(providers[provider_code]))
					else:
						key = country + " " + type
						if key in winners:
							winner_rate = normalize_price(winners[key][0])
							if winner_rate < current_rate:
								better_deal += "%s [%s]\t%s %s %s %s %s\n" % (country_name, country, type, current_rate, providers[provider_code], winner_rate, str(winners[key][1]))
								for winner in winners[key][1]:
									counters[winner] += 1
						
				else:
					output += "%s %s not available\n" % (country, type)
			else:
				output += "unknown " + str(provider_code) + "\n"
	output += "\n\nBETTER DEALS\n"
	output += better_deal
	output += "\nWINNER COUNTERS\n"
	for winner in counters:
		output += "<b>%s:</b> %s\n" % (winner, counters[winner])
	return output
		

if __name__ == "__main__":
	check_prices()
