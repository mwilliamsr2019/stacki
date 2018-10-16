import pytest
from stack.checklist import Backend, State, StateMessage
import time

class TestBackend:
	
	def test_isKnownState(self):
		b = Backend('sd-stacki-111', 'default', 'default')
		sm1 = StateMessage('10.25.241.111', State.DHCPDISCOVER, False, time.time())
		sm2 = StateMessage('10.25.241.111', State.Autoyast_Sent, False, time.time())
		b.stateArr.append(sm1)
		b.stateArr.append(sm2)

		sm3 = StateMessage('10.25.241.111', State.Rebooting_HDD, False, time.time())
		sm4 = StateMessage('10.25.241.111', State.Autoyast_Sent, True, time.time())

		assert b.isKnownState(sm3.state) == False
		assert b.isKnownState(sm4.state) == True

		sm2.isError = True
		assert b.isKnownState(sm4.state) == False

	def test_isPostPkgInstallStage(self):
		b = Backend('sd-stacki-111', 'default', 'default')
		sm1 = StateMessage('10.25.241.111', State.DHCPDISCOVER, False, time.time())
		sm2 = StateMessage('10.25.241.111', State.Autoyast_Sent, False, time.time())
		b.stateArr.append(sm1)
		b.stateArr.append(sm2)
		assert b.isPostPkgInstallStage() == False

		sm3 = StateMessage('10.25.241.111', State.Ludicrous_Populated, False, time.time())
		sm4 = StateMessage('10.25.241.111', State.Set_Bootaction_OS, False, time.time())
		b.stateArr.append(sm3)
		b.stateArr.append(sm4)
		assert b.isPostPkgInstallStage() == True

	def test_lastSuccessfulState(self):
		b = Backend('sd-stacki-111', 'default', 'default')
		assert b.lastSuccessfulState() == None

		sm1 = StateMessage('10.25.241.111', State.DHCPDISCOVER, False, time.time())
		b.stateArr.append(sm1)
		assert b.lastSuccessfulState() == sm1

		sm2 = StateMessage('10.25.241.111', State.Autoyast_Sent, True, time.time())
		b.stateArr.append(sm2)
		assert b.lastSuccessfulState() == sm1

	def test_copyAttributes(self):
		b = Backend('sd-stacki-111', 'default', 'default')
		sm1 = StateMessage('10.25.241.111', State.DHCPDISCOVER, False, time.time())
		sm2 = StateMessage('10.25.241.111', State.Autoyast_Sent, False, time.time())
		b.stateArr.append(sm1)
		b.stateArr.append(sm2)
		b.ipList = ['10.25.241.111']
		b.macList = ['ac:de:ef:dd:11:11']
		b.installKernel = 'kernel1'
		b.installRamdisk = 'ramdisk1'

		b1 = Backend('sd-stacki-112', 'default', 'default')
		smb1 = StateMessage('10.25.241.112', State.DHCPOFFER, False, time.time())
		b1.stateArr.append(smb1)
		b1.ipList = ['10.25.241.112']
		b1.macList = ['ac:de:ef:dd:11:12']
		b1.installKernel = 'kernel2'
		b1.installRamdisk = 'ramdisk2'
		b.copyAttributes(b1)

		assert b.hostName == 'sd-stacki-112'
		assert b.ipList[0] == '10.25.241.112'
		assert b.macList[0] == 'ac:de:ef:dd:11:12'
		assert b.installKernel == 'kernel2'
		assert b.installRamdisk == 'ramdisk2'
		assert b.stateArr[0].state == State.DHCPDISCOVER

class TestState:

	def test_nextState(self):
		assert State.Install_Wait.nextState() == None
		assert State.Installation_Stalled.nextState() == None
		assert State.Reboot_Okay.nextState() == None
		assert State.Root_Sent.nextState() == State.Cracklib_Dict_Sent
		assert State.Set_DB_Partitions.nextState() == State.Set_Bootaction_OS
		assert State.TFTP_RRQ.nextState() == State.VMLinuz_RRQ_Install
		assert State.Partition_XML_Present.nextState() == State.Ludicrous_Started

class TestStateMessage:

	def test_isEqual(self):
		sm1 = StateMessage('10.25.241.111', State.DHCPDISCOVER, False, time.time())
		sm2 = StateMessage('10.25.241.111', State.Autoyast_Sent, False, time.time())
		assert sm1.isEqual(sm2) == False

		sm3 = StateMessage('10.25.241.111', State.Set_Bootaction_OS, True, time.time())
		sm4 = StateMessage('10.25.241.111', State.Set_Bootaction_OS, False, time.time())
		assert sm3.isEqual(sm4) == False

		sm3.isError = False
		assert sm3.isEqual(sm4) == True
