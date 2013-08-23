import json

with open('config.json') as f:
	config = json.load(f)

def clean_dict(adict):
	for key in adict.keys():
		value = adict[key]
		if value.__class__ in [dict]:
			clean_dict(value)
		elif value.__class__ in [list]:
			value = map(lambda s: str(s), value)
		else:
			value = str(value)
		del adict[key]
		adict[str(key)] = value


clean_dict(config)

