import subprocess

def run_command(command):
	p = subprocess.Popen(['/usr/sbin/asterisk', '-nrx', command], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result = p.communicate()[0]
        try:
            p.terminate()
            print "COMMAND TERMINATED BY OBELISK!!!"
        except:
            pass
        return result
