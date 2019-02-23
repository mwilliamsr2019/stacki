# @copyright@
# Copyright (c) 2006 - 2018 Teradata
# All rights reserved. Stacki(r) v5.x stacki.com
# https://github.com/Teradata/stacki/blob/master/LICENSE.txt
# @copyright@
from datetime import datetime
from enum import Enum

class Backend:
	"""
	Object that encapsulates all backend attributes relevant
	to monitor installation
	"""
	def __init__(self, hostName, installaction, osaction):
		self.hostName = hostName
		self.installaction = installaction
		self.osaction = osaction
		self.ipList = []
		self.macList = []
		self.stateArr = []
		self.dhcpStateArr = []
		self.osKernel = None
		self.osRamdisk = None
		self.osArgs = None
		self.installKernel = None
		self.installRamdisk = None
		self.installArgs = None

	def __str__(self):
		l = []
		l.append('########## Attributes of %s - Backend ###########' % self.hostName)
		l.append('IP Addr = %s' % ','.join(self.ipList))
		l.append('MAC = %s' % ','.join(self.macList))
		l.append('OS Kernel = %s' % self.osKernel)
		l.append('OS Ramdisk = %s' % self.osRamdisk)
		l.append('OS Args = %s' % self.osArgs)
		l.append('Install Kernel = %s' % self.installKernel)
		l.append('Install Ramdisk = %s' % self.installRamdisk)
		l.append('Install Args = %s' % self.installArgs)
		l.append('#####################')
		return '\n'.join(l)

	# Test is Backend Installation is in the
	def isPostPkgInstallStage(self):
		arr = self.stateArr
		for a in reversed(arr):
			if a.state == State.Set_Bootaction_OS and \
				not a.isError:
				return True

		return False

	#
	# Checks if Backend installation has already progressed
	# through the State st.
	#
	def isKnownState(self, st):
		arr = self.stateArr
		for a in arr:
			if a.state == st and not a.isError:
				return True

		return False

	# Return the last successful StateMessage object
	def lastSuccessfulState(self):
		if not self.stateArr:
			return None

		for i in range(len(self.stateArr) - 1, -1, -1):
			if not self.stateArr[i].isError:
				return self.stateArr[i]
		return None

	# Copy all attributes (except stateArr) from Backend object b
	def copyAttributes(self, b):
		self.hostName = b.hostName
		self.installaction = b.installaction
		self.osaction = b.osaction
		self.ipList = b.ipList
		self.macList = b.macList
		self.osKernel = b.osKernel
		self.osRamdisk = b.osRamdisk
		self.osArgs = b.osArgs
		self.installKernel = b.installKernel
		self.installRamdisk = b.installRamdisk
		self.installArgs = b.installArgs

class State(Enum):
	"""
	Enum that represents various installation stages.
	"""
	DHCPDISCOVER = 10
	DHCPOFFER = 20
	DHCPREQUEST = 30
	DHCPACK = 40
	DHCPNACK = 42
	DHCPDECLINE = 46
	TFTP_RRQ = 50
	VMLinuz_RRQ_Install = 60
	Initrd_RRQ = 70
	Config_Sent = 80
	Common_Sent = 90
	Root_Sent = 100
	Cracklib_Dict_Sent = 110
	Bind_Sent = 120
	SLES_Img_Sent = 130
	Autoyast_Sent = 140
	SSH_Open = 150
	AUTOINST_Present = 160
	Partition_XML_Present = 170
	Ludicrous_Started = 180
	Ludicrous_Populated = 190
	Set_DB_Partitions = 200
	Set_Bootaction_OS = 210
	Rebooting_HDD = 220
	Reboot_Okay = 230
	Install_Wait = 500
	Installation_Stalled = 1000

	def nextState(self):
		try:
			s = State(self.value + 10)
			return s
		except:
			return None

class StateMessage:
	"""
	Object that encapsulates system test message attributes
	"""
	def __init__(self, ipAddr, state, isError, time, msg='', isAddedToRedis=False):
		self.ipAddr = ipAddr
		self.state = state
		self.isError = isError
		self.time = time
		self.msg = msg
		self.isAddedToRedis = isAddedToRedis

	def __str__(self):
		print_str = 'IP = %s, %s State = %s, Success = %s' % \
			(self.ipAddr, self.convertTimestamp(), self.state, not self.isError)

		if self.msg:
			print_str = 'IP = %s, %s State = %s, Success = %s, Message = %s' % \
			(self.ipAddr, self.convertTimestamp(), self.state, not self.isError, self.msg)

		return print_str

	# Check if all attributes except isAddedToRedis, time is equal
	def __eq__(self, sm):
		if self.ipAddr == sm.ipAddr and \
			self.state == sm.state and \
			self.msg == sm.msg and \
			self.isError == sm.isError:
				return True

		return False

	def convertTimestamp(self):
		return datetime.utcfromtimestamp(self.time) \
			.strftime('%Y-%m-%d %H:%M:%S')
