#!/usr/bin/env python3

"""
Created by Waldmensch aka Waldmaus in 2023.

Inspired by:
 - https://github.com/RalfZim/venus.dbus-fronius-smartmeter (Inspiration)
 - https://github.com/victronenergy/velib_python/blob/master/dbusdummyservice.py (Template)
 - https://github.com/iobroker-community-adapters/ioBroker.sma-em/ (SMA Protocol)

This code and its documentation can be found on: https://github.com/Waldmensch1/venus.dbus-sma-smartmeter
Used https://github.com/victronenergy/velib_python/blob/master/dbusdummyservice.py as basis for this service.
Reading information from the SMA-EM Smart Meter or Sunny HM2.0 via Speedwire Broadcast puts the info on dbus.

"""
from gi.repository import GLib
from vedbus import VeDbusService
import socket
import struct
import platform
import argparse
import logging
from logging.handlers import RotatingFileHandler
import sys
import os
import threading

MULTICAST_IP = "239.12.255.254"
MULTICAST_PORT = 9522

# our own packages
sys.path.insert(1, os.path.join(
    os.path.dirname(__file__), '../ext/velib_python'))

os.makedirs('/var/log/dbus-sma-smartmeter', exist_ok=True) 
logging.basicConfig(
    format = '%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
    datefmt = '%Y-%m-%d %H:%M:%S',
    level = logging.DEBUG,
    handlers = [
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler = RotatingFileHandler('/var/log/dbus-sma-smartmeter/current.log', maxBytes=200000, backupCount=5)
handler.setLevel(logging.DEBUG)
handler.setFormatter(formatter)
logger.addHandler(handler)

class DbusSMAEMService(object):
    def __init__(self, servicename, deviceinstance, productname='SMA-EM Speedwire Bridge', connection='SMA-EM Service'):

        self._protocol_points = {
			'SMASusyID': {'name': 'SMA Device SUSy-ID'                     , 'update': False, 'addr': 18, 'length': 2, 'unit': ''},
			'SMASerial': {'name': 'SMA Device Serial Number'               , 'update': False, 'addr': 20, 'length': 4, 'unit': ''},
			'TimeTick':  {'name': 'SMA Time Tick Counter (32-bit overflow)', 'update': True , 'addr': 24, 'length': 4, 'unit': 'ms'}
		}

        self._hardware = {
            0  : {'name' : 'UNKNOWN',  'serial' : 0, 'sw' : '', 'active' : False},
            270: {'name' : 'SMA-EM10', 'serial' : 0, 'sw' : '', 'active' : False}, 
            349: {'name' : 'SMA-EM20', 'serial' : 0, 'sw' : '', 'active' : False}, 
            372: {'name' : 'SHM2.0',   'serial' : 0, 'sw' : '', 'active' : False},
        }

        self._obis_points = {
            # real values
            0x00010400: {'name': 'pregard',        'length': 4, 'factor': 1/10,      'unit': 'W',   'value': 0, 'path': ''},
            0x00010800: {'name': 'pregardcounter', 'length': 8, 'factor': 1/3600000, 'unit': 'kWh', 'value': 0, 'path': '/Ac/Energy/Forward'},
            0x00020400: {'name': 'surplus',        'length': 4, 'factor': 1/10,      'unit': 'W',   'value': 0, 'path': ''},
            0x00020800: {'name': 'surpluscounter', 'length': 8, 'factor': 1/3600000, 'unit': 'kWh', 'value': 0, 'path': '/Ac/Energy/Reverse'},
            0x00200400: {'name': 'L1_voltage',     'length': 4, 'factor': 1/1000,    'unit': 'V',   'value': 0, 'path': '/Ac/L1/Voltage'},
            0x00340400: {'name': 'L2_voltage',     'length': 4, 'factor': 1/1000,    'unit': 'V',   'value': 0, 'path': '/Ac/L2/Voltage'},
            0x00480400: {'name': 'L3_voltage',     'length': 4, 'factor': 1/1000,    'unit': 'V',   'value': 0, 'path': '/Ac/L3/Voltage'},
            0x00150400: {'name': 'L1_pregard',     'length': 4, 'factor': 1/10,      'unit': 'W',   'value': 0, 'path': ''},
            0x00290400: {'name': 'L2_pregard',     'length': 4, 'factor': 1/10,      'unit': 'W',   'value': 0, 'path': ''},
            0x003D0400: {'name': 'L3_pregard',     'length': 4, 'factor': 1/10,      'unit': 'W',   'value': 0, 'path': ''},
            0x00160400: {'name': 'L1_surplus',     'length': 4, 'factor': 1/10,      'unit': 'W',   'value': 0, 'path': ''},
            0x002a0400: {'name': 'L2_surplus',     'length': 4, 'factor': 1/10,      'unit': 'W',   'value': 0, 'path': ''},
            0x003E0400: {'name': 'L3_surplus',     'length': 4, 'factor': 1/10,      'unit': 'W',   'value': 0, 'path': ''},
            0x90000000: {'name': 'sw_version_raw', 'length': 4, 'factor': 1 ,        'unit': '',    'value': 0, 'path': ''},
            # calculated values
            0x00000001: {'name': 'power',          'length': 0, 'factor': 1,         'unit': 'W',   'value': 0, 'path': '/Ac/Power'},
            0x00000002: {'name': 'L1_power',       'length': 0, 'factor': 1,         'unit': 'W',   'value': 0, 'path': '/Ac/L1/Power'},
            0x00000003: {'name': 'L2_power',       'length': 0, 'factor': 1,         'unit': 'W',   'value': 0, 'path': '/Ac/L2/Power'},
            0x00000004: {'name': 'L2_power',       'length': 0, 'factor': 1,         'unit': 'W',   'value': 0, 'path': '/Ac/L3/Power'},
            0x00000005: {'name': 'L1_current',     'length': 0, 'factor': 1,         'unit': 'A',   'value': 0, 'path': '/Ac/L1/Current'},
            0x00000006: {'name': 'L2_current',     'length': 0, 'factor': 1,         'unit': 'A',   'value': 0, 'path': '/Ac/L2/Current'},
            0x00000007: {'name': 'L3_current',     'length': 0, 'factor': 1,         'unit': 'A',   'value': 0, 'path': '/Ac/L3/Current'},
        }

        self._dbusservice = VeDbusService(servicename)
        logger.info('Connected to dbus, DbusSMAEMService class created')
        logger.debug("%s /DeviceInstance = %d" %
                      (servicename, deviceinstance))

        # Create the management objects, as specified in the ccgx dbus-api document
        self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
        self._dbusservice.add_path(
            '/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
        self._dbusservice.add_path('/Mgmt/Connection', connection)

        # Create the mandatory objects
        self._dbusservice.add_path('/DeviceInstance', deviceinstance)
        self._dbusservice.add_path('/ProductId', 16)
        self._dbusservice.add_path('/ProductName', productname)
        self._dbusservice.add_path('/FirmwareVersion', 0)
        self._dbusservice.add_path('/HardwareVersion', 'UNKNOWN')
        self._dbusservice.add_path('/Serial', 0)
        self._dbusservice.add_path('/Connected', 1)
        self._dbusservice.add_path('/UpdateIndex', 0)

        for obis_value in self._obis_points.values():
            if obis_value['path'] != '':
                self._dbusservice.add_path(
                    obis_value['path'], obis_value['value'], writeable=True, onchangecallback=self._handlechangedvalue)

        self._sock = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("", MULTICAST_PORT))

        mreq = struct.pack("4sl", socket.inet_aton(
            MULTICAST_IP), socket.INADDR_ANY)
        self._sock.setsockopt(
            socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        threading.Thread(target=self._alive, args=(self._sock,)).start()

    def _alive(self, sock):
        logger.info('Socket Thread started')
        while True:
           self._update(sock.recv(1024))

    def _update(self, data):

        try:
            arrlen = len(data)

            sma = str(data[0:3], 'ascii')
            #logger.info(sma + ' length: ' + str(arrlen))
            if sma == 'SMA' and arrlen > 100:

                SMASusyID = int.from_bytes(data[18:20], 'big')
                SMASerial = int.from_bytes(data[20:24], 'big')
                # logger.info('SMASusyID: ' + str(SMASusyID) + ' SMASerial: ' + str(SMASerial))

                if SMASusyID not in self._hardware:
                    SMASusyID = 0

                if self._hardware[SMASusyID]['active'] == False:
                    self._hardware[SMASusyID]['serial'] = SMASerial
                    self._dbusservice['/HardwareVersion'] = self._hardware[SMASusyID]['name']
                    self._dbusservice['/Serial'] = self._hardware[SMASusyID]['serial']

                pos = 28

                while (pos < arrlen):

                    # Get obis value as 32 bit number
                    obis_num = int.from_bytes(data[pos: pos + 4], 'big')

                    if obis_num not in self._obis_points:

                        # check for end of message
                        if obis_num == 0 and pos == arrlen - 4:
                            break

                        # Extract length from obis number, second byte is the length
                        offset = int.from_bytes(data[pos + 2: pos + 3], 'big')

                        # Only 4 or 8 is allowed for offset since all known OBIS values have the length 4 or 8
                        # Add 4 for the OBIS value itself.
                        if offset == 4 or offset == 8:
                            pos += offset + 4
                        else:
                            pos += 4 + 4

                        continue

                    length = self._obis_points[obis_num]['length']
                    pos += 4

                    # Read obis message value as 32 or 64 bit unsigned int value
                    val = 0
                    if length == 4:
                        val = int.from_bytes(data[pos: pos + length], 'big')

                    elif length == 8:
                        val = int.from_bytes(data[pos: pos + length], 'big')

                    else:
                        logger.info(
                            "Only OBIS message length of 4 or 8 is support, current length is" + length)

                    # Convert raw value to final value
                    self._obis_points[obis_num]['value'] = round(
                        val * self._obis_points[obis_num]['factor'], 2)

                    # Set read address to next obis value
                    pos += length

                # calculate the power values
                self._obis_points[0x00000001]['value'] = round(self._obis_points[0x00010400]['value'] - self._obis_points[0x00020400]['value'], 2)
                self._obis_points[0x00000002]['value'] = round(self._obis_points[0x00150400]['value'] - self._obis_points[0x00160400]['value'], 2)
                self._obis_points[0x00000003]['value'] = round(self._obis_points[0x00290400]['value'] - self._obis_points[0x002a0400]['value'], 2)
                self._obis_points[0x00000004]['value'] = round(self._obis_points[0x003D0400]['value'] - self._obis_points[0x003E0400]['value'], 2)
                self._obis_points[0x00000005]['value'] = round((self._obis_points[0x00150400]['value'] - self._obis_points[0x00160400]['value']) / self._obis_points[0x00200400]['value'], 2)
                self._obis_points[0x00000006]['value'] = round((self._obis_points[0x00290400]['value'] - self._obis_points[0x002a0400]['value']) / self._obis_points[0x00340400]['value'], 2)
                self._obis_points[0x00000007]['value'] = round((self._obis_points[0x003D0400]['value'] - self._obis_points[0x003E0400]['value']) / self._obis_points[0x00480400]['value'], 2)

                if self._hardware[SMASusyID]['active'] == False:
                    swr = self._obis_points[0x90000000]['value']
                    sw = str((swr >> 24) & 0xFF)
                    sw += '.' + str((swr >> 16) & 0xFF)
                    sw += '.' + str((swr >> 8) & 0xFF)
                    sw += '.' + chr(swr & 0xFF)
                    self._hardware[SMASusyID]['sw'] = sw
                    self._dbusservice['/FirmwareVersion'] = self._hardware[SMASusyID]['sw']
                    self._hardware[SMASusyID]['active'] = True

                for obis_value in self._obis_points.values():
                    if obis_value['path'] != '':
                        self._dbusservice[obis_value['path']] = obis_value['value']

                # increment UpdateIndex - to show that new data is available
                index = self._dbusservice['/UpdateIndex'] + 1
                if index > 255:
                    index = 0
                self._dbusservice['/UpdateIndex'] = index

        except:
            logger.info("WARNING: Could not read from SMA Energy Meter")
            self._dbusservice['/Ac/Power'] = 0

        return True

    def _handlechangedvalue(self, path, value):
        logger.debug("someone else updated %s to %s" % (path, value))
        return True  # accept the change

def main():

    from dbus.mainloop.glib import DBusGMainLoop
    # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
    DBusGMainLoop(set_as_default=True)

    pvac_output = DbusSMAEMService(
        servicename='com.victronenergy.grid.smaem', deviceinstance=0)

    mainloop = GLib.MainLoop()
    mainloop.run()

if __name__ == "__main__":
    main()
