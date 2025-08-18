#! /usr/bin/python3

import os
import re
import socket
import sys
from itertools import chain
from textwrap import wrap
from urllib.parse import quote

import dbus

bus = dbus.SystemBus()

device_id = 'CLS:PRINTER;CMD:EPSON;DES:Thermal Printer;MFG:Phomemo;MDL:'

def scan_bluetooth():
    try:
        bluez = bus.get_object('org.bluez', '/')
    except dbus.exceptions.DBusException:
        print("WARNING: no bluetooth interface", file=sys.stderr)
        return

    re_name_pattern = re.compile(r'^(Mr\.in(.*)|Q[0-9]{3}[A-Z][0-9]{10}|T02)$')

    manager = dbus.Interface(bluez, 'org.freedesktop.DBus.ObjectManager')

    objects = manager.GetManagedObjects()
    device_interface = dbus.String('org.bluez.Device1')

    for path, interfaces in objects.items():
        properties = interfaces.get(device_interface, None)
        if properties is None:
            continue

        name = properties.get('Name', None)
        if name is None or properties.get('Icon', None) != 'printer':
            continue

        m = re_name_pattern.match(name)
        if not m:
            continue

        model = m.group(2) or m.group(1)

        address = properties['Address']
        device_uri = f'phomemo://{address.replace(":", "")}'
        device_make_and_model = 'Phomemo ' + model

        print(f'direct {device_uri} "{device_make_and_model}" "{device_make_and_model} bluetooth {address}" "{device_id}{model} (BT);"')

class find_class(object):
    def __init__(self, class_):
        self._class = class_

    def __call__(self, device):
        # first, let's check the device
        if device.bDeviceClass == self._class:
            return True
        # ok, transverse all devices to find an
        # interface that matches our class
        for cfg in device:
            # find_descriptor: what's it?
            intf = usb.util.find_descriptor(
                                        cfg,
                                        bInterfaceClass=self._class
                                )
            if intf is not None:
                return True

        return False

def scan_usb():
    printers = chain(
        usb.core.find(find_all=1, custom_match=find_class(7), idVendor=0x0493),
        usb.core.find(find_all=1, custom_match=find_class(7), idVendor=0x0483),
    )

    for printer in printers:
            for cfg in printer:
                intf = usb.util.find_descriptor(cfg, bInterfaceClass=7)
                if intf is None:
                    continue
                Interface = intf.bInterfaceNumber
                break
            if printer.idProduct == 0xb002:
                model = 'M02'
            elif printer.idProduct == 0x8760:
                model = 'M110'
            elif printer.idProduct == 0x5740:
                model = 'M110S'
            else:
                model = f'Unknown(0x{printer.idProduct:04x})'
            usb.util.get_langids(printer)
            SerialNumber = usb.util.get_string(printer, printer.iSerialNumber)
            device_uri = f'usb://{quote(printer.manufacturer)}/{quote(printer.product)}?serial={SerialNumber}&interface={Interface}'
            device_make_and_model = f'Phomemo {model}'
            print(f'direct {device_uri} "{device_make_and_model}" "{device_make_and_model} USB {SerialNumber}" "{device_id}{model} (USB);"')


if len(sys.argv) == 1:
    scan_bluetooth()
    try:
        import usb.core
        import usb.util
    except ModuleNotFoundError:
        print("WARNING: Please install python3-usb to support usb-discovery", file=sys.stderr)
        exit(0)
    scan_usb()
    exit(0)

device_uri = os.environ.get('DEVICE_URI')
if device_uri is None:
    exit(1)

uri = device_uri.split('://')

if uri[0] != 'phomemo':
    exit(1)

bdaddr = ":".join(wrap(uri[1], 2))

try:
    print('STATE: +connecting-to-device')
    sock = socket.socket(socket.AF_BLUETOOTH, proto=socket.BTPROTO_RFCOMM)
    sock.connect((bdaddr, 1))
    print('STATE: +sending-data')
    with os.fdopen(sys.stdin.fileno(), 'rb', closefd=False) as stdin:
        while True:
            data = stdin.read(8192)
            size = len(data)
            if size == 0:
                break
            sock.sendall(data)
            print('DEBUG: sent %d' % (size))
except OSError as btErr:
    print("ERROR: Can't open Bluetooth connection: " + str(btErr), file=sys.stderr)
    exit(1)
except socket.error as SockErr:
    print("ERROR: Cannot write data: " + str(SockErr), file=sys.stderr)
    exit(1)

try:
    # we need to wait the printer answer before closing the socket
    # otherwise the print is stopped
    print('STATE: +receiving-data')
    sock.settimeout(8)
    while True:
        received = sock.recv(28)
        print('DEBUG: ' + " 0x".join("%02x" % b for b in received))
except:
    pass
exit(0)
