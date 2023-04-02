# SMA Speedwire interpreter

import socket
import struct

MULTICAST_IP = "239.12.255.254"
MULTICAST_PORT = 9522

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("", MULTICAST_PORT))

mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_IP), socket.INADDR_ANY)
sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

obis_points = {
    # real values
    0x00010400: {'name': 'pregard',        'length': 4, 'factor': 1/10,      'unit': 'W',   'value': 0, 'path': ''},
    0x00010800: {'name': 'pregardcounter', 'length': 8, 'factor': 1/3600000, 'unit': 'kWh', 'value': 0, 'path': '/Ac/Energy/Forward'},
    0x00020400: {'name': 'surplus',        'length': 4, 'factor': 1/10,      'unit': 'W',   'value': 0, 'path': ''},
    0x00020800: {'name': 'surpluscounter', 'length': 8, 'factor': 1/3600000, 'unit': 'kWh', 'value': 0, 'path': '/Ac/Energy/Reverse'},
    0x00200400: {'name': 'L1_voltage',     'length': 4, 'factor': 1/1000,    'unit': 'V',   'value': 0, 'path': '/Ac/L1/Voltage'},
    0x00340400: {'name': 'L2_voltage',     'length': 4, 'factor': 1/1000,    'unit': 'V',   'value': 0, 'path': '/Ac/L2/Voltage'},
    0x00480400: {'name': 'L3_voltage',     'length': 4, 'factor': 1/1000,    'unit': 'V',   'value': 0, 'path': '/Ac/L3/Voltage'},
    #0x001F0400: {'name': 'L1_current',     'length': 4, 'factor': 1/1000,    'unit': 'A',   'value': 0, 'path': '/Ac/L1/Current'},
    #0x00330400: {'name': 'L2_current',     'length': 4, 'factor': 1/1000,    'unit': 'A',   'value': 0, 'path': '/Ac/L2/Current'},
    #0x00470400: {'name': 'L3_current',     'length': 4, 'factor': 1/1000,    'unit': 'A',   'value': 0, 'path': '/Ac/L3/Current'},
    
    0x00150400: {'name': 'L1_pregard',     'length': 4, 'factor': 1/10,      'unit': 'W',   'value': 0, 'path': ''},
    0x00290400: {'name': 'L2_pregard',     'length': 4, 'factor': 1/10,      'unit': 'W',   'value': 0, 'path': ''},
    0x003D0400: {'name': 'L3_pregard',     'length': 4, 'factor': 1/10,      'unit': 'W',   'value': 0, 'path': ''},
    
    0x00160400: {'name': 'L1_surplus',     'length': 4, 'factor': 1/10,      'unit': 'W',   'value': 0, 'path': ''},
    0x002a0400: {'name': 'L2_surplus',     'length': 4, 'factor': 1/10,      'unit': 'W',   'value': 0, 'path': ''},
    0x003E0400: {'name': 'L3_surplus',     'length': 4, 'factor': 1/10,      'unit': 'W',   'value': 0, 'path': ''},

    # calculated values
    0x00000001: {'name': 'power',          'length': 0, 'factor': 1,         'unit': 'W',   'value': 0, 'path': '/Ac/Power'},
    0x00000002: {'name': 'L1_power',       'length': 0, 'factor': 1,         'unit': 'W',   'value': 0, 'path': '/Ac/L1/Power'},
    0x00000003: {'name': 'L2_power',       'length': 0, 'factor': 1,         'unit': 'W',   'value': 0, 'path': '/Ac/L2/Power'},
    0x00000004: {'name': 'L2_power',       'length': 0, 'factor': 1,         'unit': 'W',   'value': 0, 'path': '/Ac/L3/Power'},
    0x00000005: {'name': 'L1_current',     'length': 0, 'factor': 1,         'unit': 'A',   'value': 0, 'path': '/Ac/L1/Current'},
    0x00000006: {'name': 'L2_current',     'length': 0, 'factor': 1,         'unit': 'A',   'value': 0, 'path': '/Ac/L2/Current'},
    0x00000007: {'name': 'L3_current',     'length': 0, 'factor': 1,         'unit': 'A',   'value': 0, 'path': '/Ac/L3/Current'},
}


def decode_speedwire(data):
    arrlen = len(data)

    sma = str(data[0:3], 'ascii')
    # print(sma + ' length: ' + str(arrlen))
    if sma == 'SMA' and arrlen > 100:

        # 270 = SMAEM10, 349 = SMAEM20, 372 = SHM2.0
        SMASusyID = int.from_bytes(data[18:20], 'big')
        SMASerial = int.from_bytes(data[20:24], 'big')
        # print('SMASusyID: ' + str(SMASusyID) + ' SMASerial: ' + str(SMASerial))

        pos = 28

        while (pos < arrlen):

            # Get obis value as 32 bit number
            obis_num = int.from_bytes(data[pos: pos + 4], 'big')

            if obis_num not in obis_points:

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

            length = obis_points[obis_num]['length']
            pos += 4

            # Read obis message value as 32 or 64 bit unsigned int value
            val = 0
            if length == 4:
                val = int.from_bytes(data[pos: pos + length], 'big')

            elif length == 8:
                val = int.from_bytes(data[pos: pos + length], 'big')

            else:
                print(
                    "Only OBIS message length of 4 or 8 is support, current length is" + length)

            # Convert raw value to final value
            obis_points[obis_num]['value'] = round(
                val * obis_points[obis_num]['factor'], 2)

            # Set read address to next obis value
            pos += length

        # calculate the power values
        obis_points[0x00000001]['value'] = round(obis_points[0x00010400]['value'] - obis_points[0x00020400]['value'], 2)
        obis_points[0x00000002]['value'] = round(obis_points[0x00150400]['value'] - obis_points[0x00160400]['value'], 2)
        obis_points[0x00000003]['value'] = round(obis_points[0x00290400]['value'] - obis_points[0x002a0400]['value'], 2)
        obis_points[0x00000004]['value'] = round(obis_points[0x003D0400]['value'] - obis_points[0x003E0400]['value'], 2)
        obis_points[0x00000005]['value'] = round((obis_points[0x00150400]['value'] - obis_points[0x00160400]['value']) / obis_points[0x00200400]['value'], 2)
        obis_points[0x00000006]['value'] = round((obis_points[0x00290400]['value'] - obis_points[0x002a0400]['value']) / obis_points[0x00340400]['value'], 2)
        obis_points[0x00000007]['value'] = round((obis_points[0x003D0400]['value'] - obis_points[0x003E0400]['value']) / obis_points[0x00480400]['value'], 2)

        for obis_values in obis_points.values():
            print(obis_values['name'] + ": " +
                  str(obis_values['value']) + obis_values['unit'])


while True:
    decode_speedwire(sock.recv(10240))
