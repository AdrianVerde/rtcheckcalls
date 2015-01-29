from twisted.web.resource import Resource
from twisted.web.util import redirectTo
from datetime import datetime
import time
import os

from obelisk import session

from obelisk.model import Model
from obelisk.asterisk.model import SipPeer, VoiceMailMessage
from obelisk.tools import html

from obelisk.templates import print_template

class VoiceMailResource(Resource):
    def __init__(self):
	Resource.__init__(self)

    def render_POST(self, request):
	logged = session.get_user(request)
	if not logged:
		return redirectTo("/", request)

	ext = logged.voip_id

	parts = request.path.split("/")
	if len(parts) > 4:
		action = parts[2]
		user_ext = parts[3]
		msg_id = parts[4]
		if action == 'delete':
			ext = self.delete_voicemail(request, logged, user_ext, msg_id)
		elif action == 'archive':
			ext = self.archive_voicemail(request, logged, user_ext, msg_id)
	
	return redirectTo("/voicemail/"+ext, request)

    def delete_voicemail(self, request, logged, user_ext, msg_id):
	model = Model()
	msg = model.query(VoiceMailMessage).filter_by(msg_id=msg_id, mailboxuser=user_ext).first()
	if msg and msg.recording and (msg.mailboxuser == logged.voip_id or logged.admin):
		mb_user = msg.mailboxuser
		number = msg.msgnum
		msgdir = msg.dir
		model.session.delete(msg)
		model.session.commit()
		# reorder other messages in the folder
		msgs = model.query(VoiceMailMessage).filter_by(mailboxuser=mb_user)
		for amsg in msgs:
			if amsg.msgnum > number and amsg.dir == msgdir:
				amsg.msgnum -= 1
		model.session.commit()
		return mb_user
	return logged.voip_id

    def archive_voicemail(self, request, logged, user_ext, msg_id):
	model = Model()
	msg = model.query(VoiceMailMessage).filter_by(msg_id=msg_id, mailboxuser=user_ext).first()
	if msg and msg.recording and (msg.mailboxuser == logged.voip_id or logged.admin):
		mb_user = msg.mailboxuser
		number = msg.msgnum
		msgdir = msg.dir
		destdir = '/var/spool/asterisk/voicemail/default/%s/Old' % (logged.voip_id,)
		msg.dir = destdir
		msg.msgnum = 500
		model.session.commit()
		# reorder other messages in the folder
		msgs = model.query(VoiceMailMessage).filter_by(mailboxuser=mb_user)
		lastmsg = -1
		for amsg in msgs:
			if amsg.msgnum > number and amsg.dir == msgdir:
				amsg.msgnum -= 1
			if amsg.dir == destdir and amsg.msgnum > lastmsg and not amsg.msg_id == msg_id:
				lastmsg = amsg.msgnum
		msg.msgnum = lastmsg + 1
				
		model.session.commit()
		return mb_user
	return logged.voip_id

 
    def render_GET(self, request):
	logged = session.get_user(request)
	if not logged:
		return redirectTo("/", request)

	parts = request.path.split("/")
	if len(parts) > 3 and parts[2] == 'message':
		msg_id = parts[3]
		return self.render_voice_message(request, logged, msg_id)
	if len(parts) > 2 and logged.admin:
		user_ext = parts[2]
	else:
		user_ext = logged.voip_id

	request.setHeader('Cache-Control', 'no-cache, must-revalidate') # http1.1
	request.setHeader('Pragma', 'no-cache') # http1.0
	res = self.render_mailbox(user_ext)
        model = Model()
        peer = model.query(SipPeer).filter_by(regexten=user_ext).first()
	return print_template('content-pbx-lorea', {'content': res, 'user': user_ext, 'username': peer.name})

    def render_voice_message(self, request, logged, msg_id):
	model = Model()
	msg = model.query(VoiceMailMessage).filter_by(msg_id=msg_id).first()
	if msg and msg.recording and (msg.mailboxuser == logged.voip_id): # no admin here:
		request.setHeader('Content-Description', 'File Transfer')
		request.setHeader('Content-Type', 'application/octet-stream')
		request.setHeader('Content-Disposition', 'attachment; filename=recording-'+msg_id+'-.ogg')
		request.setHeader('Content-Transfer-Encoding', 'binary')
		#request.setHeader('Expires', '0')
		request.setHeader('Content-Length', len(msg.recording))
		return msg.recording
	return "no access"

    def render_mailbox(self, user_ext):
	output = "<h1>Correo de voz</h1>\n"
	model = Model()
	model.session.commit() # refresh session
	all_messages = model.query(VoiceMailMessage).filter_by(mailboxuser=user_ext)
	folders = set()
	for message in all_messages:
		folders.add(message.dir)
	folders = list(folders)
	folders.sort()
	for folder in folders:
		result = []
		messages = model.query(VoiceMailMessage).filter_by(mailboxuser=user_ext, dir=folder)
		output += "<h2>"+os.path.basename(folder)+"</h2>\n"
		for message in messages:
			actions2 = ""
			if message.msg_id:
				audio = html.format_audio('/voicemail/message/' + message.msg_id)
				actions = '<form method="POST" action="/voicemail/delete/%s/%s"><input type="hidden" name="msg_id" value="%s" /><input type="hidden" name="user_ext" value="%s" /><input type="submit" name="submit" value="Borrar" /></form>' % (user_ext, message.msg_id, message.msg_id, user_ext)
				if folder.endswith('INBOX'):
					actions2 += '<form method="POST" action="/voicemail/archive/%s/%s"><input type="hidden" name="msg_id" value="%s" /><input type="hidden" name="user_ext" value="%s" /><input type="submit" name="submit" value="Archivar" /></form>' % (user_ext, message.msg_id, message.msg_id, user_ext)
			else:
				audio = ""
				actions = ""
			result.append([message.callerid, time.ctime(message.origtime), str(message.duration), audio, actions, actions2])
		output += html.format_table([['origen', 'fecha', 'duracion', 'audio', 'actions', '']] + result)
	return output

    def getChild(self, name, request):
        return self

