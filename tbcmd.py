#!/usr/bin/env python3

import sys, re, json, asyncio
from argparse import ArgumentParser, Namespace
import bleak
import requests

from bleak import BleakClient, BleakScanner
from tb_protocol import *

#Transmit Handle 0x0021
TX_CHAR_UUID = '0000fff5-0000-1000-8000-00805F9B34FB'
#Read Handle 0x0024
RX_CHAR_UUID = '0000fff3-0000-1000-8000-00805F9B34FB'


def mac_addr(x):
    if not re.match("[0-9a-f]{2}([-:]?)[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$", x.lower()):
        raise ValueError()
    return x


parser = ArgumentParser()
subparsers = parser.add_subparsers(help='action', dest='command', required=True)

sub = subparsers.add_parser('scan', help = "Scan for ThermoBeacon devices")
sub.add_argument('-mac', type=mac_addr, required=False)
sub.add_argument('-t', type=int, default = 20, metavar='<Scan duration, seconds>', required=False)
sub = subparsers.add_parser('identify', help = "Identify a device")
sub.add_argument('-mac', type=mac_addr, required=True)
sub = subparsers.add_parser('query', help = "Query device for details")
sub.add_argument('-mac', type=mac_addr, required=True)
sub = subparsers.add_parser('dump', help = "Dump logged data")
sub.add_argument('-mac', type=mac_addr, required=True)


args = parser.parse_args()

#print(args.command)


def main():
    cmd = args.command
    if cmd=='scan':
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(scan())
        except KeyboardInterrupt:
            print()
            return
    elif cmd=='identify':
        identify(args.mac)
        return
    elif cmd=='dump':
        dump(args.mac)
        return
    print('Not yet implemented')

async def scan():
    scanner = BleakScanner()
    scanner.register_detection_callback(detection_callback)
    await scanner.start()
    await asyncio.sleep(540)
    await scanner.stop()


def detection_callback(device, advertisement_data):
    name = advertisement_data.local_name
    if name is None:
        return
    if name != 'ThermoBeacon':
        return
    msg = advertisement_data.manufacturer_data
    #print(device.rssi)
    for key in msg.keys():
        bvalue = msg[key]
        mac = device.address.lower()
        if len(bvalue)==18:
            data = TBAdvData(key, bvalue)
            payload = {
                "mac": mac,
                "rssi": int(device.rssi),
                "id": data.id,
                "humidity": float(data.hum),
                "temperature": float(data.tmp),
                "battery": float(data.btr),
                "uptime": int(data.upt),
                "button": bool(data.btn),
            }
            r = requests.post('https://nr.doebi.at/thermobeacon', data=json.dumps(payload))
            print('[{0}] [{6:02x}] T= {1:5.2f}\xb0C, H = {2:3.2f}%, Button:{4}, Battery : {5:02.0f}%, UpTime = {3:8.0f}s'.\
                  format(mac, data.tmp, data.hum, data.upt, 'On ' if data.btn else 'Off', data.btr, data.id))
        else:
            data = TBAdvMinMax(key, bvalue)
            print('[{0}] [{5:02x}] Max={1:5.2f}\xb0C at {2:.0f}s, Min={3:5.2f}\xb0C at {4:.0f}s'.\
                  format(mac, data.max, data.max_t, data.min, data.min_t, data.id))


'''
'''
def dump(address):
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(_dump(address))
    except bleak.exc.BleakDBusError as dber:
        print(dber.dbus_error)
    except Exception as exc:
        print('///'+str(exc))

async def _dump(address):
    client = BleakClient(address)
    try:
        await client.connect(timeout=10)
        print('connectd')
    except Exception as exc:
        print('exception ' + str(exc))
        return
    try:
        print(client.is_connected)

        cmd = TBCmdQuery()
        await client.write_gatt_char(TX_CHAR_UUID, cmd.get_msg())
        data = await client.read_gatt_char(RX_CHAR_UUID)
        resp = TBMsgQuery(data)
        print('01:'+data.hex())

        await client.start_notify(RX_CHAR_UUID, dump_callback)
        cmd_dump = bytes([TB_COMMAND_DUMP, 0, 0, resp.count&0xff, (resp.count>>8)&0xff, (resp.count>>16)&0xff, 1])
        cnt = 0
        while cnt<resp.count:
            c = 15 if resp.count-cnt>15 else resp.count-cnt
            cmd = TBCmdDump(cnt, c)
            cmd_dump = cmd.get_msg()
            cnt += c
            #print('cmd ', cmd_dump.hex())
            await client.write_gatt_char(TX_CHAR_UUID, cmd_dump)
        await asyncio.sleep(.5)
        data = await client.read_gatt_char(RX_CHAR_UUID)
        print(data.hex())
    finally:
        await client.disconnect()

def dump_callback(sender: int, data: bytearray):
    if data is None:
        return
    try:
        hdata = data.hex()
        msg = TBMsgDump(data)
        print(msg.offset, msg.count, msg.data)
        #print(f"{sender}: {hdata}")
    except Exception as exc:
        print(str(exc))

'''
'''
def identify(address):
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(_identify(address))
    except bleak.exc.BleakDBusError as dber:
        print(dber.dbus_error)
    except Exception as exc:
        print('///'+str(exc))

async def _identify(address):
    client = BleakClient(address)
    try:
        await client.connect(timeout=10)
        print('connectd')
    except Exception as exc:
        print('exception ' + str(exc))
        return

    try:
        cmd = TBCmdIdentify()
        await client.write_gatt_char(TX_CHAR_UUID, cmd.get_msg())
    finally:
        await client.disconnect()

if __name__ == '__main__':
    main()
