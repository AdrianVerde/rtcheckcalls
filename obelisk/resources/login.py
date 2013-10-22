from twisted.web.resource import Resource
from twisted.web.util import redirectTo

from datetime import datetime

import md5
import json

from obelisk.config import config
from obelisk.model import Model, WebSession, User
from obelisk.asterisk.model import SipPeer

resource = None

class LoginResource(Resource):
    def __init__(self):
	global resource
	Resource.__init__(self)
	resource = self
    def render_GET(self, request):
        return redirectTo("/", request)

    def render_POST(self, request):
	action = request.args['action'][0]
	login = request.args['login'][0]
	password = request.args['password'][0]
	return self.login(login, password, request)

    def check_password_ext(self, user_ext, password):
	return self.check_password(None, password, user_ext)

    def check_password(self, username, password, user_ext=None):
	model = Model()
	peer = None
	if user_ext:
		peer = model.query(SipPeer).filter_by(regexten=user_ext).first()
	else:
		peer = model.query(SipPeer).filter_by(name=username).first()
	if peer:
		username = peer.name
		user_input = md5.new(username + ":asterisk:" + password).hexdigest()
		hashed = peer.md5secret
		if peer.secret and not hashed:
			hashed = md5.new(username + ":asterisk:" + peer.secret).hexdigest()
		if hashed == user_input:
			return peer
	return False

    def login(self, login, password, request, email=''):
        action = request.args.get('action', ['login'])
	peer = self.check_password(login, password)
	if peer:
		user_ext = peer.regexten
		model = Model()
		user = model.get_user_fromext(user_ext)
		if not user:
			user = User(user_ext)
			if email:
				user.email = email
			model.session.add(user)
			model.session.commit()
		session_id = str(request.getSession().uid)
		web_session = model.query(WebSession).filter_by(session_id=session_id).first()
		if not web_session:
			web_session = WebSession(session_id=session_id, timestamp=datetime.now(), user=user)

		model.session.add(web_session)
		model.session.commit()
                if action == 'login':
		    return redirectTo("/user/"+user_ext, request)
                elif action == 'login_agent':
		    return json.dumps({'user': user_ext, 'credit': float(user.credit), 'admin': user.admin})
	return redirectTo("/", request)
