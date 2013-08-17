import json

filename = "/etc/asterisk/prefixes.conf"

from obelisk.pricechecker import get_winners

ext2country_cache = {}

def update_cache(prices):
    global ext2country_cache
    for country in prices:
        for label in prices[country]:
            data = prices[country][label]
            ext2country_cache[data[2].replace('+', '00')] = [country, label]

def parse_prices():
	f = open(filename, "r")

	prices = {}
	label = ""
	label_price = ""
	type = ""
	extension = ""
	for line in f.readlines():
		
		if line.startswith(";"):
			pass
		elif line.startswith("["):
			label = line[1:line.find("]")]
			extension = ""
			if ";" in line:
				extension = line[line.find(";")+1:].strip().split()[0]
			label_parts = label.rsplit("-", 1)
			label = label_parts[0]
			label_price = ""
			type = label_parts[1]
		# exten => _0035537[12345678]X.,1,Macro(callto,${albania-fix-provider}/${EXTEN},120,0.046)
		elif "callto" in line:
			call_type = "unknown"
			price = line[line.rfind(",")+1:line.rfind(")")]
			if label_price == "":
				label_price = price
			elif price != label_price:
				print "price mismatch for", label, price, label_price
			provider = line[line.find('$')+2: line.find('provider')+8]
			if not len(line.split(",")) >= 6:
				continue
			if not label in prices:
				prices[label] = {}
			if type == 'fixmob':
				prices[label]['fix'] =  [price, provider, extension]
				prices[label]['mob'] =  [price, provider, extension]
			else:
				prices[label][type] =  [price, provider, extension]
	f.close()
        update_cache(prices)
	return prices

def ext2country(ext):
    if not ext2country_cache:
        update_cache(parse_prices())
    if ext == "0":
        return ['bo', 'fh']
    if len(ext) < 3:
        return ['service', 'local']
    if len(ext) < 5:
        return ['extension', 'local']
    if ext.startswith('00'):
        if ext[0:5]  in ext2country_cache:
            return ext2country_cache[ext[0:5]]
        elif ext[0:4]  in ext2country_cache:
            return ext2country_cache[ext[0:4]]
        elif ext[0:3]  in ext2country_cache:
            return ext2country_cache[ext[0:3]]
    return ['unknown ', 'unknown']

def list_prices():
	prices = parse_prices()
	labels = prices.keys()
	labels.sort()
	output = ""

	for label in labels:
		output += "<h2>"+label+"</h2>"
		for call_type in prices[label]:
			price, provider = prices[label][call_type]
			if price == "0.0":
				price = "gratis"
			else:
			   price = float(price) + 0.001
			output += call_type + ": " + str(price) + "<br />"
	return output

def list_prices_json():
	prices = parse_prices()
	labels = prices.keys()
	labels.sort()
	output = "{"

	for label in labels:
		first = True
		output += "'"+label+"': {"
		for call_type in prices[label]:
			price, provider, extension  = prices[label][call_type]
			if first:
				first = False
				output += "'ext': '" + str(extension) + "',"
			if price == "0.0":
				price = "'gratis'"
			else:
			   price = float(price) + 0.001
			output += "'" + call_type + "': " + str(price) + ","
		output += "},"
	output += "}"
	return output


if __name__ == "__main__":
        ext2country("0034972267124")
	parse_prices()
	print list_prices_json()
