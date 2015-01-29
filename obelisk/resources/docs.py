from twisted.web.resource import Resource


from obelisk.templates import print_template

from obelisk import session
from obelisk.model import Model
from obelisk.asterisk.model import SipPeer

class DocsResource(Resource):
    def render_GET(self, request):
	parts = request.path.split("/")
	if len(parts) == 2:
		parts.append('contents')
	if len(parts) > 2:
		section = parts[2]
		try:
			content = print_template('docs/' + section, {})
		except:
			content = "la seccion no existe"
	        user = session.get_user(request)
	        if user:
	            model = Model()
	            peer = model.query(SipPeer).filter_by(regexten=user.voip_id).first()
	            return print_template("content-pbx-lorea", {'content': content, 'user': user.voip_id, 'username': peer.name})

		return print_template("content-pbx-lorea", {'content': content})
    def getChild(self, name, request):
        return self
