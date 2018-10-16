import pytest
import queue
from stack.checklist import State, StateMessage
from stack.checklist.threads import MQProcessor, InstallHashProcessor, LogParser, BackendExec, CheckTimeouts
import stack.util
from subprocess import Popen
import time

class TestChecklistDaemons:

	def test_LogParser_dhcp(self):
		q = queue.Queue()
		logParser =  LogParser(r'/var/log/messages', q)
		logParser.daemon = True
		logParser.start()
		s = "fe-hostname dhcpd: DHCPREQUEST for 8.8.8.8 " \
			"(1.1.1.1) from 55:55:55:55:55:55 via br0  avtest"
		expectedStMsg = StateMessage('8.8.8.8', State.DHCPREQUEST, \
			False, time.time())

		matchedFlag = False
		logParser.processDhcp(s)
		while not logParser.localQ.empty():
			sm = logParser.localQ.get()
			if sm.isEqual(expectedStMsg):
				matchedFlag = True
				break
		logParser.shutdownFlag.set()

		while not q.empty():
			sm = q.get()
			if sm.isEqual(expectedStMsg):
				matchedFlag = True
				break

		assert matchedFlag == True

	def test_LogParser_tftp(self):
		q = queue.Queue()
		logParser =  LogParser(r'/var/log/messages', q)
		logParser.daemon = True
		logParser.start()
		s = '8.8.8.8 - - [02/Oct/2018:17:22:56 +0000] "GET ' \
			'/install/sbin/profile.cgi?os=sles&arch=x86_64&np=4 HTTP/1.1" 200 51261'
		s = "fe-hostname in.tftpd[3339]: RRQ from 8.8.8.8 " \
			"filename pxelinux.cfg/MACaddr"
		expectedStMsg = StateMessage('8.8.8.8', State.TFTP_RRQ, \
			False, time.time(), 'pxelinux.cfg/MACaddr')

		matchedFlag = False
		logParser.processTftp(s)
		while not logParser.localQ.empty():
			sm = logParser.localQ.get()
			if sm.isEqual(expectedStMsg):
				matchedFlag = True
				break
		logParser.shutdownFlag.set()

		while not q.empty():
			sm = q.get()
			print(sm)
			if sm.isEqual(expectedStMsg):
				matchedFlag = True
				break

		assert matchedFlag == True

	def test_LogParser_SSLAccessLog(self):
		q = queue.Queue()
		logParser =  LogParser(r'/var/log/apache2/ssl_access_log', q)
		logParser.daemon = True
		logParser.start()
		s = '8.8.8.8 - - [02/Oct/2018:17:22:56 +0000] "GET ' \
			'/install/sbin/profile.cgi?os=sles&arch=x86_64&np=4 HTTP/1.1" 200 51261'
		expectedStMsg = StateMessage('8.8.8.8', State.Autoyast_Sent,
			False, time.time())

		matchedFlag = False
		logParser.parseSSLAccessLog(s)
		while not logParser.localQ.empty():
			sm = logParser.localQ.get()
			if sm.isEqual(expectedStMsg):
				matchedFlag = True
				break
		logParser.shutdownFlag.set()

		while not q.empty():
			sm = q.get()
			if sm.isEqual(expectedStMsg):
				matchedFlag = True
				break

		assert matchedFlag == True

	def test_LogParser_AccessLog(self):
		q = queue.Queue()
		logParser =  LogParser(r'/var/log/apache2/access_log', q)
		logParser.daemon = True
		logParser.start()
		s = '8.8.8.8 - - [14/Feb/2019:21:23:55 +0000] "GET ' \
			'/install/pallets/SLES/12/sp3/sles/x86_64/boot/x86_64/cracklib-dict-full.rpm' \
			' HTTP/1.1" 200 3257877 "-" "-"'
		expectedStMsg = StateMessage('8.8.8.8',State.Cracklib_Dict_Sent,
			False, time.time())

		matchedFlag = False
		logParser.parseAccessLog(s)
		while not logParser.localQ.empty():
			sm = logParser.localQ.get()
			if sm.isEqual(expectedStMsg):
				matchedFlag = True
				break
		logParser.shutdownFlag.set()

		while not q.empty():
			sm = q.get()
			if sm.isEqual(expectedStMsg):
				matchedFlag = True
				break

		assert matchedFlag == True
