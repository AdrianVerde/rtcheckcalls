from twisted.web.resource import Resource
from twisted.web.util import redirectTo

from obelisk import session

from obelisk.model import Model
from obelisk.resources import login
from obelisk.asterisk.model import SipPeer

from obelisk.templates import print_template
from obelisk.asterisk.users import change_password
from obelisk.session import get_user

class ChangePassResource(Resource):
    def render_POST(self, request):
	logged = get_user(request)
	if not logged:
		return returnTo("/", request)
	args = {}
        for a in request.args:
            args[a] = request.args[a][0]

	user_ext = logged.voip_id
	if logged and 'newpassword2' in args and args['newpassword2'] and 'newpassword1' in args and args['newpassword1'] and (('password' in args and args['password']) or logged.admin):
		if 'ext' in args and args['ext'] and logged.admin:
			user_ext = args['ext']
		password = args['password']
		logged_name = logged.voip_id
		if (logged.admin and not logged.voip_id == user_ext) or login.resource.check_password_ext(user_ext, password):
			newpassword1 = args['newpassword1']
			newpassword2 = args['newpassword2']
			if newpassword1 == newpassword2:
				change_password(user_ext, newpassword1)
				return redirectTo('/user/' + user_ext, request)
			else:
				return redirectTo('/password/' + user_ext, request)
	return redirectTo('/', request)

    def render_GET(self, request):
	res = None
	logged = session.get_user(request)
	if not logged:
		return redirectTo('/', request)

	parts = request.path.split("/")
	if len(parts) > 2 and logged.admin:
		user_ext = parts[2]
	else:
		user_ext = logged.voip_id
	
	content = print_template('password', {'ext': user_ext})
        peer = model.query(SipPeer).filter_by(regexten=logged.voip_id).first()
	return print_template('content-pbx-lorea', {'content': content, 'username': peer.name, 'user': logged.voip_id})

    def getChild(self, name, request):
        return self
