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
from vedbus import VeDbusService
import socket
import struct
import platform
import argparse
import logging
import sys
import os

MULTICAST_IP = "239.12.255.254"
MULTICAST_PORT = 9522

# our own packages
sys.path.insert(1, os.path.join(
    os.path.dirname(__file__), '../ext/velib_python'))


class DbusSMAEMService(object):
    def __init__(self, servicename, deviceinstance, productname='SMA-EM', connection='SMA-EM Service'):

        self._obis_points = {
            # real values
            0x00010400: {'name': 'pregard',        'length': 4, 'factor': 1/10,      'unit': 'W',   'value': 0, 'path': ''},
            0x00010800: {'name': 'pregardcounter', 'length': 8, 'factor': 1/3600000, 'unit': 'kWh', 'value': 0, 'path': '/Ac/Energy/Forward'},
            0x00020400: {'name': 'surplus',        'length': 4, 'factor': 1/10,      'unit': 'W',   'value': 0, 'path': ''},
            0x00020800: {'name': 'surpluscounter', 'length': 8, 'factor': 1/3600000, 'unit': 'kWh', 'value': 0, 'path': '/Ac/Energy/Reverse'},
            0x00200400: {'name': 'L1_voltage',     'length': 4, 'factor': 1/1000,    'unit': 'V',   'value': 0, 'path': '/Ac/L1/Voltage'},
            0x00340400: {'name': 'L2_voltage',     'length': 4, 'factor': 1/1000,    'unit': 'V',   'value': 0, 'path': '/Ac/L2/Voltage'},
            0x00480400: {'name': 'L3_voltage',     'length': 4, 'factor': 1/1000,    'unit': 'V',   'value': 0, 'path': '/Ac/L3/Voltage'},
            0x001F0400: {'name': 'L1_current',     'length': 4, 'factor': 1/1000,    'unit': 'A',   'value': 0, 'path': '/Ac/L1/Current'},
            0x00330400: {'name': 'L2_current',     'length': 4, 'factor': 1/1000,    'unit': 'A',   'value': 0, 'path': '/Ac/L2/Current'},
            0x00470400: {'name': 'L3_current',     'length': 4, 'factor': 1/1000,    'unit': 'A',   'value': 0, 'path': '/Ac/L3/Current'},
            # calculated values
            0x00000001: {'name': 'power',          'length': 0, 'factor': 1,         'unit': 'W',   'value': 0, 'path': '/Ac/Power'},
            0x00000002: {'name': 'L1_power',       'length': 0, 'factor': 1,         'unit': 'W',   'value': 0, 'path': '/Ac/L1/Power'},
            0x00000003: {'name': 'L2_power',       'length': 0, 'factor': 1,         'unit': 'W',   'value': 0, 'path': '/Ac/L2/Power'},
            0x00000004: {'name': 'L2_power',       'length': 0, 'factor': 1,         'unit': 'W',   'value': 0, 'path': '/Ac/L3/Power'},
        }

        self._dbusservice = VeDbusService(servicename)
        logging.info('Connected to dbus, DbusSMAEMService class created')
        logging.debug("%s /DeviceInstance = %d" %
                      (servicename, deviceinstance))

        # Create the management objects, as specified in the ccgx dbus-api document
        self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
        self._dbusservice.add_path(
            '/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
        self._dbusservice.add_path('/Mgmt/Connection', connection)

        # Create the mandatory objects
        self._dbusservice.add_path('/DeviceInstance', deviceinstance)
        self._dbusservice.add_path('/ProductId', 0)
        self._dbusservice.add_path('/ProductName', productname)
        self._dbusservice.add_path('/FirmwareVersion', 0)
        self._dbusservice.add_path('/HardwareVersion', 0)
        self._dbusservice.add_path('/Connected', 1)

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

        while True:
            self._update(self._sock.recv(10240))

    def _update(self, data):

        try:
            arrlen = len(data)

            sma = str(data[0:3], 'ascii')
            # logging.info(sma + ' length: ' + str(arrlen))
            if sma == 'SMA' and arrlen > 100:

                # 270 = SMAEM10, 349 = SMAEM20, 372 = SHM2.0
                SMASusyID = int.from_bytes(data[18:20], 'big')
                SMASerial = int.from_bytes(data[20:24], 'big')
                # logging.info('SMASusyID: ' + str(SMASusyID) + ' SMASerial: ' + str(SMASerial))

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
                        logging.info(
                            "Only OBIS message length of 4 or 8 is support, current length is" + length)

                    # Convert raw value to final value
                    self._obis_points[obis_num]['value'] = round(
                        val * self._obis_points[obis_num]['factor'], 2)

                    # Set read address to next obis value
                    pos += length

                # calculate the power values
                self._obis_points[0x00000001]['value'] = round(
                    self._obis_points[0x00010400]['value'] - self._obis_points[0x00020400]['value'], 2)
                self._obis_points[0x00000002]['value'] = round(
                    self._obis_points[0x00340400]['value'] * self._obis_points[0x001F0400]['value'], 2)
                self._obis_points[0x00000003]['value'] = round(
                    self._obis_points[0x00340400]['value'] * self._obis_points[0x00330400]['value'], 2)
                self._obis_points[0x00000004]['value'] = round(
                    self._obis_points[0x00480400]['value'] * self._obis_points[0x00470400]['value'], 2)

                for obis_value in self._obis_points.values():
                    if obis_value['path'] != '':
                        self._dbusservice[obis_value['path']
                                          ] = obis_value['value']

        except:
            logging.info("WARNING: Could not read from SMA Energy Meter")
            self._dbusservice['/Ac/Power'] = 0

        # increment UpdateIndex - to show that new data is available
        index = self._dbusservice['/UpdateIndex'] + 1
        if index > 255:
            index = 0
        self._dbusservice['/UpdateIndex'] = index

        return True

    def _handlechangedvalue(self, path, value):
        logging.debug("someone else updated %s to %s" % (path, value))
        return True  # accept the change


# === All code below is to simply run it from the commandline for debugging purposes ===

# It will created a dbus service called com.victronenergy.pvinverter.output.
# To try this on commandline, start this program in one terminal, and try these commands
# from another terminal:
# dbus com.victronenergy.pvinverter.output
# dbus com.victronenergy.pvinverter.output /Ac/Energy/Forward GetValue
# dbus com.victronenergy.pvinverter.output /Ac/Energy/Forward SetValue %20

def main():
    logging.basicConfig(level=logging.DEBUG)

    pvac_output = DbusSMAEMService(
        servicename='com.victronenergy.grid.smaem', deviceinstance=0)


if __name__ == "__main__":
    main()