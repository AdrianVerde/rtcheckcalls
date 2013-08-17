import subprocess
import os
import memory
import resource
import time

import obelisk
from obelisk.asterisk import cli
from obelisk.resources import sse

def run_command(cmd):
	return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()[0]

def get_cli_clients():
	result = run_command(['/usr/bin/lsof', '/var/run/asterisk/asterisk.ctl'])
        result = result.split("\n")
        return len(result)-1
        

# uptime
def get_obelisk_uptime():
	curr_time = time.time()
	running_time = curr_time - obelisk.starttime
	return running_time

def get_uptime():
	return run_command("uptime").strip()

def get_asterisk_uptime():
	res = filter(lambda s: ":" in s, run_command(['asterisk', '-nrx', 'core show uptime']).split("\n"))
	return map(lambda s: s.split(":")[1].strip(), res)

def get_asterisk_version():
	return run_command(['asterisk', '-nrx', 'core show version'])

# ip tinc
def get_tinc_ip():
	ifconfig = run_command(["ifconfig","pln"])
	return ifconfig[ifconfig.find("inet addr:")+10:ifconfig.find("P-t-P")-2]

def freespace(p):
    """
    Returns the number of free bytes on the drive that ``p`` is on
    """
    s = os.statvfs(p)
    return s.f_bsize * s.f_bavail

def get_dundi_peers():
	res = run_command(['asterisk', '-nrx', 'dundi show peers']).split("\n")
	res = filter(lambda s: 'OK' in s, res)
	return len(res)

def get_sip_peers():
	res = run_command(['asterisk', '-nrx', 'sip show peers']).split("\n")
	res = filter(lambda s: 'OK' in s or 'LAGGED' in s, res)
	return len(res)


# peers
#print run_command(["asterisk", "-nrx", "sip show peers"])

# memory
def get_memory():
	result = {}
	f = open("/proc/meminfo")
	data = f.readlines()
	f.close()
	KB = 1024.0
	memtotal = int(data[0].split()[1]) / KB
	memfree = int(data[1].split()[1]) / KB
	result['total'] = memtotal
	result['free'] = memfree
	result['used'] = memtotal-memfree
	result['self-resident'] = memory.resident() / memory.MB
	result['self-memory'] = memory.memory() / memory.MB
	return result

	#print resource.getrusage(resource.RUSAGE_SELF)

def get_report_data():
	mem = get_memory()
	output = {}
	output['obelisk-starttime'] = time.ctime(obelisk.starttime)
	output['asterisk-uptime'] = get_asterisk_uptime()
	output['asterisk-version'] = get_asterisk_version()
	output['uptime'] = get_uptime()
	output['tinc_ip'] = get_tinc_ip()
	output['dundi-peers'] = get_dundi_peers()
	output['sip-peers'] = get_sip_peers()
	output['freespace'] = freespace("/") / (memory.MB * 1024)
	output['sse_threads'] = len(sse.resource._connections.keys())
	return output

def get_report():
	mem = get_memory()
	asterisk_uptime = get_asterisk_uptime()
	output = ""
	output += """<p><b>uptime</b>: %s</p>
		<p><b>obelisk start time</b>: %s</p>
		<p><b>asterisk</b>:</p>
		<p>uptime: %s</p>
		<p>last reload: %s</p>
		<p>version: %s</p>
		<p><b>tinc ip</b>: %s</p>
		<p><b>memory</b></p>
		<p>total: %.1f MB</p>
		<p>free: %.1f MB</p>
		<p>obelisk: %.1f (%.1f) MB</p>
		<p><b>free disk space</b>: %.1f GB</p>
		<p><b>sse connections</b>: %d</p>
		<p><b>dundi peers</b>: %d</p>
		<p><b>sip peers</b>: %d</p>
	""" % (get_uptime(), time.ctime(obelisk.starttime), asterisk_uptime[0], asterisk_uptime[1], get_asterisk_version(), get_tinc_ip(), mem['total'], mem['free'], mem['self-memory'], mem['self-resident'], freespace("/") / (memory.MB * 1024), len(sse.resource._connections.keys()), get_dundi_peers(), get_sip_peers())

	return output

if __name__ == "__main__":
	print get_cli_clients()
	print get_uptime()
	print get_tinc_ip()
	print get_memory()
	print freespace("/") / (memory.MB * 1024)
	print get_report()

