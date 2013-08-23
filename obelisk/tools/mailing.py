import smtplib
from email.mime.text import MIMEText

from obelisk.config import config
from obelisk.model import Model, User
from obelisk.asterisk.model import SipPeer

def send(destination, subject, body):
    """
    Sends mail to one destination.
    """
    mail_config = config.get('mail', None)
    if not mail_config or not mail_config.get('sender'):
        print "Obelisk mail module not configured"
        return

    if not subject or not body:
        print "No body or subject!!!"
        return

    sender = mail_config['sender']

    msg = MIMEText(body)

    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = destination

    s = smtplib.SMTP(mail_config.get('smtp', 'localhost'))
    s.sendmail(sender, [destination], msg.as_string())
    s.quit()

def mass_send(subject, body, password):
    """
    Sends mail to all users.
    """
    model = Model()
    sent = set()
    for user in model.query(User):
        if user.email and not user.email in sent:
            sent.add(user.email)
            peer = model.query(SipPeer).filter_by(regexten=user.voip_id).first()
            print ' * mass mail to', peer.name, user.voip_id, user.email
            if config['mail']['password'] == password:
                print ' * really sending to', user.email
                send(user.email, subject, body)
    

