from obelisk.config import config

tpl_cache = {}

def print_template(name, variables):
        if not tpl_cache.get(name):
	    f = open('templates/'+name+'.html')
	    data = f.read()
	    f.close()
            tpl_cache[name] = data

        data = tpl_cache[name]

	if 'logo' in config:
		variables['logo'] = config['logo']
	else:
		variables['logo'] = 'voip'
	for var in variables:
		tpl_name = "%%"+var+"%%"
		if tpl_name in data:
			data = data.replace(tpl_name, str(variables[var]))
	return data

if __name__ == '__main__':
	print print_template('home-pbx-lorea', {'LINKS': '<li>foo</li>'})
