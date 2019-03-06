# Copyright (c) 2006 - 2017 Teradata
# All rights reserved. Stacki(r) v5.x stacki.com
# https://github.com/Teradata/stacki/blob/master/LICENSE.txt
# @copyright@

from . import Switch, SwitchException
import os
import time
import pexpect
from contextlib import suppress
from stack.expectmore import ExpectMore, ExpectMoreException


class SwitchDellX1052(Switch):
	"""
	Class for interfacing with a Dell x1052 switch.
	"""

	def __init__(self, *args, **kwargs):
		"""Override __init__ to set up expectmore. Let the superclass __init__ do everything else."""
		self.proc = ExpectMore(
			prompts = ["console#", "console.config.#",]
		)
		super().__init__(*args, **kwargs)

	def supported(*cls):
		return [
			('Dell', 'x1052'),
		]

	def connect(self):
		"""Connect to the switch"""
		try:
			# Don't connect if we are already connected.
			if self.proc.isalive():
				return

			self.proc.start(cmd = f"ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -tt {self.switch_ip_address}")
			self.proc.conversation(
				response_pairs = [
					("User Name:", self.username),
					("Password:", self.password),
				]
			)
		except ExpectMoreException:
			raise SwitchException("Couldn't connect to the switch")

	def disconnect(self):
		"""Disconnect from the switch if a connection is active."""
		# if we've already disconnected, don't try again.
		if not self.proc.isalive():
			return

		# q will exit out of an existing scrollable more/less type of prompt
		# Probably not necessary, but a bit safer
		self.proc.say(cmd = "q")
		# We might be in a configure console, which means we'll need a second exit
		# and expectmore wont find the EOF it is looking for this first time.
		with suppress(ExpectMoreException):
			self.proc.end(quit_cmd = "exit")

		# Exit if we successfully shut down the process.
		if not self.proc.isalive():
			return

		# Try one more time to quit because we might have been in the
		# configure console.
		self.proc.end(quit_cmd = "exit")

	def _expect(self, look_for, custom_timeout=15):
		try:
			self.child.expect(look_for, timeout=custom_timeout)
		except pexpect.exceptions.TIMEOUT:
			# print "Giving SSH time to close gracefully...",
			for _ in range(9, -1, -1):
				if not self.child.isalive():
					break
				time.sleep(1)
			debug_info = str(str(self.child.before) + str(self.child.buffer) + str(self.child.after))
			self.__exit__()
			raise SwitchException(self.switch_ip_address + " expected output '" + look_for +
							"' from SSH connection timed out after " +
							str(custom_timeout) + " seconds.\nBuffer: " + debug_info)
		except pexpect.exceptions.EOF:
			self.__exit__()
			raise SwitchException("SSH connection to " + self.switch_ip_address + " not available.")

	def get_mac_address_table(self):
		"""Download the mac address table"""
		time.sleep(1)
		command = 'show mac address-table'
		self.child.expect('console#', timeout=60)
		with open('/tmp/%s_mac_address_table' % self.switchname, 'wb') as macout:
			self.child.logfile = macout
			self.child.sendline(command)
			time.sleep(1)
			self.send_spacebar(4)
			self.child.expect('console#', timeout=60)
		self.child.logfile = None

	def parse_mac_address_table(self):
		"""Parse the mac address table and return list of connected macs"""
		_hosts = []
		with open('/tmp/%s_mac_address_table' % self.switchname, 'r') as f:
			for line in f.readlines():
				if 'dynamic' in line:
					# appends line to list
					# map just splits out the port
					#   from the interface
					_hosts.append(list(
					  map(lambda x: x.split('/')[-1],
					  line.split())
					))

		return sorted(_hosts, key=lambda x: x[2])

	def get_interface_status_table(self):
		"""Download the interface status table"""
		time.sleep(1)
		command = 'show interface status'
		self.child.expect('console#', timeout=60)
		with open('/tmp/%s_interface_status_table' % self.switchname, 'wb') as macout:
			self.child.logfile = macout
			self.child.sendline(command)
			time.sleep(1)
			self.send_spacebar(4)
			self.child.expect('console#', timeout=60)
		self.child.logfile = None

	def parse_interface_status_table(self):
		"""Parse the interface status and return list of port information"""
		_hosts = []
		with open('/tmp/%s_interface_status_table' % self.switchname, 'r') as f:
			for line in f.readlines():
				if 'gi1/0/' in line:
					# appends line to list
					# map just splits out the port
					#   from the interface
					_hosts.append(list(
					  map(lambda x: x.split('/')[-1],
					  line.split())
					))

		return _hosts

	def send_spacebar(self, times=1):
		"""Send Spacebar; Used to read more of the output"""
		command = "\x20"
		for i in range(times):
			self.child.send(command)
			time.sleep(1)

	def download(self):
		"""Download the running-config from the switch to the server"""

		self.child.expect('console#', timeout=60)

		#
		# tftp requires the destination file to already exist and to be writable by all
		#
		filename = os.path.join(self.tftpdir, self.current_config)
		f = open(filename, 'w')
		f.close()
		os.chmod(filename, mode=0o777)

		cmd = "copy running-config tftp://%s/%s" % (self.stacki_server_ip,
			self.current_config)
		self.child.sendline(cmd)
		self._expect('The copy operation was completed successfully')

	def upload(self):
		"""Upload the file from the switch to the server"""

		self.child.expect('console#', timeout=60)

		cmd = "copy tftp://%s/%s temp" % (self.stacki_server_ip, self.new_config)
		self.child.sendline(cmd)

		time.sleep(2)
		self.child.sendline('Y')  # A quick Y will fix the overwrite prompt if it exists.
		self._expect('The copy operation was completed successfully')

		#
		# we remove all VLANs (2-4094) which is time consuming, so up the timeout to 30
		#
		self.child.sendline("copy temp running-config")
		self._expect('The copy operation was completed successfully', custom_timeout=30)

	def apply_configuration(self):
		"""Apply running-config to startup-config"""
		try:
			self.child.expect('console#')
			self.child.sendline('write')
			self.child.expect('Overwrite file .startup-config.*\?')
			self.child.sendline('Y')
			self._expect('The copy operation was completed successfully')
		except:
			raise SwitchException('Could not apply configuration to startup-config')

	def set_tftp_ip(self, ip):
		self.stacki_server_ip = ip
