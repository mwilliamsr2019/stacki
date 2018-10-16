#!/opt/stack/bin/python3
# @copyright@
# @copyright@
import daemon
from functools import partial
import lockfile.pidlockfile
import logging
import os
import queue
import signal
import socket
from stack.checklist import Backend, State, StateMessage
from stack.checklist.threads import MQProcessor, InstallHashProcessor, LogParser, BackendExec, CheckTimeouts
import stack.api
import sys
import threading
import zmq

class Checklist(threading.Thread):

	TIMEOUT_STR = 'Installation Stage Timeout'
	REFRESH_STATE = 1
	SUCCESS_TFTP = 0
	IGNORE_TFTP_MSG = 2

	#
	# Refresh Backend State information from database
	# and update internal State
	#
	def refreshBackendInfo(self):
		hnameBackendMap = self.getHosts()
		self.log.debug('List of hostnames = %s' % ','.join(hnameBackendMap.keys()))
		newIpBackendMap = self.getHostInterfaces(hnameBackendMap)

		# Build a bootaction dictionary for ease of access
		bootactionMap = self.getBootactions()
		self.populateBootActionInfo(newIpBackendMap.values(), bootactionMap)

		# Check if there are new hosts
		for ip in newIpBackendMap.keys():
			if ip not in self.ipBackendMap:
				self.ipBackendMap[ip] = newIpBackendMap[ip]
				continue

			if ip in self.ignoreIpList:
				self.ignoreIpList.remove(ip)

			# Update backend info
			b = newIpBackendMap[ip]
			self.ipBackendMap[ip].copyAttributes(b)

		# Delete old entries
		for ip in self.ipBackendMap.keys():
			if ip not in newIpBackendMap:
				del self.ipBackendMap[ip]

	#
	# Get list of hosts from the database and return
	# dictionary of {'hostname':backend object}
	#
	def getHosts(self):
		hnameBackendMap = {}
		op = stack.api.Call('list.host')
		for o in op:
			b = Backend(o['host'], o['installaction'], o['osaction'])
			hnameBackendMap[o['host']] = b

		return hnameBackendMap

	# Get list of host interfaces
	def getHostInterfaces(self, hnameBackendMap):
		ipBackendMap = {}

		# Get list of PXE enabled networks
		op = stack.api.Call('list.network', ['pxe=True'])
		pxeNetworkList = []
		for o in op:
			pxeNetworkList.append(o['network'])

		op = stack.api.Call('list.host.interface')
		for o in op:
			hostname = o['host']
			if o['network'] in pxeNetworkList:
				b = hnameBackendMap[hostname]
				b.ipList.append(o['ip'])
				b.macList.append(o['mac'])
				# Insert <ip, BackendObj> into dictionary
				if o['ip']:
					ipBackendMap[o['ip']] = b
		return ipBackendMap

	# Get bootactions from database
	def getBootactions(self):
		bootactionMap = {}
		op = stack.api.Call('list.bootaction')
		for o in op:
			key = o['bootaction'] + '-' + o['type']
			bootactionMap[key] = o
		return bootactionMap

	#
	# Get Kernel, Ramdisk, Args associated with bootaction
	# for a backend
	#
	def populateBootActionInfo(self, backendList, bootactionMap):
		for b in backendList:
			key = b.installaction + '-install'
			o = bootactionMap[key]
			b.installKernel  = o['kernel']
			b.installRamdisk = o['ramdisk']
			b.installArgs    = o['args']

			key = b.osaction + '-os'
			o = bootactionMap[key]
			b.osKernel  = o['kernel']
			b.osRamdisk = o['ramdisk']
			b.osArgs    = o['args']

	#
	# Gather all information relevant to monitor Backend installation
	# and store it in a dictionary for ease of access
	#
	def getBackendInfo(self):
		hnameBackendMap = self.getHosts()
		ipBackendMap = self.getHostInterfaces(hnameBackendMap)

		# Build a bootaction dictionary for ease of access
		bootactionMap = self.getBootactions()

		self.populateBootActionInfo(ipBackendMap.values(), bootactionMap)
		self.ipBackendMap = ipBackendMap

	# Find Backend object based on MAC address
	def getBackendByMac(self, mac):
		backendList = self.ipBackendMap.values()
		for b in backendList:
			if mac in b.macList:
				return b
		return None

	# Process TFTP messages based on internal state information
	def processTftp(self, sm):
		pxeFile = sm.msg.strip()
		backend = self.ipBackendMap[sm.ipAddr]
		retVal = Checklist.SUCCESS_TFTP

		# Check if TFTP message components match backend details
		if '/' in pxeFile:
			pxeArr = pxeFile.split('/')
			hexip = pxeArr[1]
			backendIpArr = backend.ipList[0].split('.')
			backendHexIp = '{:02X}{:02X}{:02X}{:02X}' \
				.format(*map(int, backendIpArr))

			#
			# Ignore TFTP pxelinux.cfg messages in the post
			# install phase
			#
			if backend.isPostPkgInstallStage() or \
				backendHexIp != pxeArr[-1]:
				retVal = Checklist.IGNORE_TFTP_MSG
		elif pxeFile == backend.installKernel:
			sm.state = State.VMLinuz_RRQ_Install
		elif pxeFile == backend.installRamdisk:
			sm.state = State.Initrd_RRQ
		elif pxeFile in backend.osKernel:
			sm.state = State.Rebooting_HDD
		else:
			retVal = Checklist.REFRESH_STATE

		return retVal

	#
	# Look through DHCP State arr and restore messages that arrived
	# within 60 seconds before TFTP messages.
	# 
	def restoreDhcpMsgs(self, sm):
		backend = self.ipBackendMap[sm.ipAddr]
		clearFlag = False
		index = -1

		# Ignore all DHCP messages in the post installation phase
		if backend.isPostPkgInstallStage():
			return

		for s in backend.dhcpStateArr:
			d = int(sm.time - s.time)

			if 0 < d < 5:
				backend.stateArr.append(s)
				clearFlag = True
				if index == -1:
					index = len(backend.stateArr)

		if clearFlag:
			if index > 0 and backend.stateArr[index-2].state not in  \
				[State.DHCPDISCOVER, State.DHCPOFFER, \
				State.DHCPACK, State.DHCPREQUEST]:
				# Delete state messages from previous install
				del backend.stateArr[0:index]
			backend.dhcpStateArr.clear()

	#
	# Process messages from the shared Queue
	#
	def processQueueMsgs(self):
		while not self.shutdownFlag.is_set():
			sm = self.queue.get()
			self.log.debug(sm)
			with self.lock:
				#
				# Ignore messages from IP's not in cluster
				# Eg: local loopback interface
				#
				if sm.ipAddr in self.ignoreIpList:
					continue
				# DHCPDISCOVER messages have mac addr in msg field
				elif sm.state == State.DHCPDISCOVER and sm.msg:
					b = self.getBackendByMac(sm.msg)
					#
					# If its a new MAC address then its time to update
					# internal state from the database.
					#
					if not b:
						self.refreshBackendInfo()
						b = self.getBackendByMac(sm.msg)
						if not b:
							continue
					sm.ipAddr = b.ipList[0]
					sm.msg = ''
				# Refresh State if IP Addr not in ipBackendMap
				elif sm.ipAddr and sm.ipAddr not in self.ipBackendMap:
					self.log.debug('refresh initiated by %s' % sm)
					self.refreshBackendInfo()
					if sm.ipAddr not in self.ipBackendMap:
						self.ignoreIpList.append(sm.ipAddr)
						continue

				# Process TFTP messages
				if sm.state == State.TFTP_RRQ and not sm.isError:
					self.restoreDhcpMsgs(sm)
					# Classify TFTP messages based on internal state
					retVal = self.processTftp(sm)
					#
					# Handle case where IP addr maybe present but
					# bootactions may have changed
					#
					if retVal == Checklist.REFRESH_STATE:
						self.refreshBackendInfo()
						retVal = self.processTftp(sm)

					if retVal == Checklist.IGNORE_TFTP_MSG:
						continue

				# Append message to the relevant Backend.stateArr
				backend   = self.ipBackendMap[sm.ipAddr]
				stateList = backend.stateArr
				currState = backend.lastSuccessfulState()
				nextState = None

				if currState:
					nextState = currState.state.nextState()	
				#
				# If State same as last state ignore this msg
				# OR
				# If this is a timeout message but it was successful
				# earlier then drop the timeout message
				#
				if (len(stateList) > 0 and sm.isEqual(stateList[-1])) or \
					(Checklist.TIMEOUT_STR in sm.msg and \
					backend.isKnownState(sm.state)):
					continue
				#
				# Discard spurious DHCP messagesto handle cases where
				# DHCP server is very chatty
				#
				elif (sm.state in [State.DHCPDISCOVER, State.DHCPOFFER, \
					State.DHCPREQUEST, State.DHCPACK] and \
					nextState and sm.state != nextState):
					backend.dhcpStateArr.append(sm)
					continue

				stateList.append(sm)

			#
			# Lazy init BackendExec thread only after
			# Autoyast_Sent StateMessage is received.
			#
			if sm.state == State.Autoyast_Sent and not sm.isError:
				# If BackendExec already exists shut it down
				if sm.ipAddr in self.ipThreadMap:
					t = self.ipThreadMap[sm.ipAddr]
					if t.isAlive():
						t.shutdownFlag.set()

				backendThread = BackendExec(sm.ipAddr, self.queue)
				self.ipThreadMap[sm.ipAddr] = backendThread
				backendThread.setDaemon(True)
				backendThread.start()

			with self.lock:
				# Sort messages based on  time
				stateList.sort(key=lambda x: x.time)

				# Add current state to Redis
				currState = backend.lastSuccessfulState()

				if currState and not currState.isError and \
					not currState.isAddedToRedis and \
					currState.state.name in self.timeThreshold:
					redisKey  = sm.ipAddr + '-' + currState.state.name
					timeout = self.timeThreshold[currState.state.name]
					self.r.set(redisKey, currState, ex=timeout)
					currState.isAddedToRedis = True

			self.log.info('#### Installation Status Messages for %s ####' % sm.ipAddr)
			for s in stateList:
				self.log.info(s)
			self.log.info('#############################################')

			if sm.state == State.Reboot_Okay:
				with self.lock:
					stateList.clear()
					backend.dhcpStateArr.clear()

	def run(self):
		self.shutdownFlag = threading.Event()

		# Set logging parameters
		self.log = logging.getLogger('checklist')
		fh = logging.FileHandler('/var/log/checklist.log')
		fileFormatter = logging.Formatter('%(message)s')
		fh.setFormatter(fileFormatter)
		fh.setLevel(logging.DEBUG)

		if 'STACKDEBUG' in os.environ:
			# STDOUT handler
			consoleLogger = logging.StreamHandler(sys.stdout)
			stdoutFormatter = logging.Formatter('%(message)s')
			consoleLogger.setFormatter(stdoutFormatter)
			consoleLogger.setLevel(logging.INFO)
			self.log.addHandler(consoleLogger)

		self.log.addHandler(fh)

		if 'STACKDEBUG' in os.environ:
			self.log.setLevel(logging.DEBUG)
		else:
			self.log.setLevel(logging.INFO)

		self.log.info('Starting chklist...')

		import redis
		try:
			self.r = redis.StrictRedis(host='localhost')
		except:
			self.log.error(self, 'cannot connect to redis')

		#
		# InstallState : Max Number of seconds before
		# which install has to progress to next state.
		#
		self.timeThreshold = {
			'DHCPDISCOVER': 60,
			'DHCPOFFER' : 60,
			'DHCPREQUEST' : 60,
			'DHCPACK' : 60,
			'TFTP_RRQ' : 60,
			'VMLinuz_RRQ_Install' : 60,
			'Initrd_RRQ'  : 60,
			'Config_Sent' : 240,
			'Common_Sent' : 240,
			'Root_Sent' : 240,
			'Cracklib_Dict_Sent' : 240,
			'Bind_Sent' : 240,
			'SLES_Img_Sent' : 240,
			'Autoyast_Sent' : 300,
			'SSH_Open' : 300,
			'AUTOINST_Present' : 360,
			'Partition_XML_Present' : 360,
			'Ludicrous_Started' : 700,
			'Ludicrous_Populated' : 1200,
			'Set_Bootaction_OS' : 360,
			'Rebooting_HDD' : 7200,
			'Reboot_Okay' : 720
		}

		self.ipBackendMap = {}
		self.ignoreIpList = []
		self.lock = threading.RLock()
		self.getBackendInfo()

		self.queue = queue.Queue()

		self.dhcpLog = LogParser(r'/var/log/messages', \
			self.queue)
		self.dhcpLog.setDaemon(True)
		self.dhcpLog.start()

		self.apacheLog = LogParser(r'/var/log/apache2/ssl_access_log', \
			self.queue)
		self.apacheLog.setDaemon(True)
		self.apacheLog.start()

		self.accessLog = LogParser(r'/var/log/apache2/access_log', \
			self.queue)
		self.accessLog.setDaemon(True)
		self.accessLog.start()

		context = zmq.Context()
		tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.mqProcessor = MQProcessor(context, tx, \
			self.queue)
		self.mqProcessor.setDaemon(True)
		self.mqProcessor.start()

		self.hashProcessor = InstallHashProcessor(context, tx, \
			self.queue)
		self.hashProcessor.setDaemon(True)
		self.hashProcessor.start()

		self.timeoutThread = CheckTimeouts(self.ipBackendMap, self.queue, self.lock)
		self.timeoutThread.setDaemon(True)
		self.timeoutThread.start()

		self.ipThreadMap = {}
		for ip, b in self.ipBackendMap.items():
			backendThread = BackendExec(ip, self.queue, False)
			backendThread.setDaemon(True)
			backendThread.start()
			self.ipThreadMap[ip] = backendThread

		self.processQueueMsgs()

def signalHandler(t, sig, frame):
	# Send Signal to threads
	t.dhcpLog.shutdownFlag.set()
	t.apacheLog.shutdownFlag.set()
	t.accessLog.shutdownFlag.set()
	t.timeoutThread.shutdownFlag.set()

	for ip, th in t.ipThreadMap.items():
		if th.is_alive():
			th.shutdownFlag.set()

	t.log.info('Exiting....')
	t.shutdownFlag.set()
	sys.exit(0)

if __name__ == "__main__":
	if 'STACKDEBUG' not in os.environ:
		lock = lockfile.pidlockfile.PIDLockFile('/var/run/%s/%s.pid' % 
			('checklist', 'checklist'))
		daemon.DaemonContext(pidfile=lock).open()

	c = Checklist()
	c.setDaemon(True)
	c.start()
	signal.signal(signal.SIGINT, partial(signalHandler, c))
	signal.signal(signal.SIGTERM, partial(signalHandler, c))
	signal.pause()
