#!/usr/bin/python
import getopt
import socket
import sys
import re
import time
import os
import subprocess
import logging
import threading
from homeassistant.const import (
	CONF_HOST,
	CONF_PORT,
)

DATA_DEVICE_REGISTER = "k_device_register"
DOMAIN = "kincony-sha"

_LOGGER = logging.getLogger(__name__)
# _LOGGER.setLevel(logging.DEBUG)


class KTransport(object):
	"""docstring for KTransport"""
	def __init__(self):
		super(KTransport, self).__init__()
		self.lock = threading.Lock()
		self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.s.settimeout(5)
		self.connected = False

	def _send(self, command):
		self.s.sendto(command.encode(), self.address)

	def _read(self):
		return self.s.recv(1024).decode('utf-8')

	def setAddress(self, address):
		self.address = address

	def getLock(self):
		return self.lock

	def call(self, command):
		if (not self.connected):
			try:
				self.s.connect(self.address)
				self.connected = True
			except:
				_LOGGER.error("cannot connect socket")

		try:
			self._send(command)
		except BrokenPipeError:
			self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self.s.settimeout(5)
			self.connected = False
			time.sleep(3)
			self.call(command)

		try:
			result = self._read()
		except Exception as e:
			_LOGGER.error("socket read error")
			_LOGGER.error(e)
			self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self.s.settimeout(5)
			self.connected = False

		return result


async def async_setup(hass, config):
	_LOGGER.info("k init")
	hass.data[DATA_DEVICE_REGISTER] = KTransport()
	return True

class KConnection(object):
	def __init__(self, s, index):
		super(KConnection, self).__init__()
		self.s = s
		self.index = index
		
	def send2K(self, action_type):
		first_run = False
		fix_every_time = False
		kcode = '255'		

		if first_run:
			result = self.s.call('RELAY-SCAN_DEVICE-NOW')
			_LOGGER.info("scan:" + result)

		if first_run or fix_every_time:
			result = self.s.call('RELAY-TEST-NOW')
			_LOGGER.info("test:" + result)

		if action_type == 'on' and self.index == 'all':
			command = 'RELAY-SET_ALL-' + kcode + ',255'
		elif action_type == 'off' and self.index == 'all':
			command = 'RELAY-SET_ALL-' + kcode + ',0'
		elif action_type == 'on':
			command = 'RELAY-SET-' + kcode + ',' + self.index + ',1'
		elif action_type == 'off':
			command = 'RELAY-SET-' + kcode + ',' + self.index + ',0'
		elif action_type == 'get':
			command = 'RELAY-READ-' + kcode + ',' + self.index
		elif action_type == 'test':
			command = 'RELAY-TEST-NOW'
		elif action_type == 'scan':
			command = 'RELAY-SCAN_DEVICE-NOW'
		elif action_type == 'error':
			command = 'zzz'

		result = self.s.call(command)

		# self.s.close()

		_LOGGER.debug("request:" + command)
		_LOGGER.debug("response:" + result)

		return result

	def send2KWithLock(self, action_type):
		with self.s.getLock():
			result = self.send2K(action_type)
		return result

	def turnOn(self):
		result = self.send2KWithLock('on')
		x = re.match("RELAY-SET-\\d+,\\d+,(\\d+),OK", result)
		if x.group(1) != "1":
			_LOGGER.warning("exit 5")


	def turnOff(self):
		result = self.send2KWithLock('off')
		x = re.match("RELAY-SET-\\d+,\\d+,(\\d+),OK", result)
		if x.group(1) != "0":
			_LOGGER.warning("exit 6")	

	def getStatus(self):
		result = self.send2KWithLock('get')
		try:
			x = re.match("RELAY-READ-\\d+,\\d+,(\\d+),OK", result)
			return x.group(1) == "1"
		except Exception as e:
			_LOGGER.error(f'cannot get status for {self.index} - result was: {result}')
			raise e
