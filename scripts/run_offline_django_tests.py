"""Run focused Django QA without DNS or outbound network connections.

Only loopback and Unix-domain sockets are allowed. No production credentials
or services are required. Network-dependent behavior must be mocked by tests.
"""
import ipaddress
import os
import runpy
import socket
import sys


def local(host):
    if host in (None, '', 'localhost', b'localhost'):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def checked_address(address):
    if isinstance(address, tuple) and not local(address[0]):
        raise OSError('Offline QA: outbound network blocked')


original_connect = socket.socket.connect
original_connect_ex = socket.socket.connect_ex
original_resolve = socket.getaddrinfo
original_sendto = socket.socket.sendto


def connect(self, address):
    checked_address(address)
    return original_connect(self, address)


def connect_ex(self, address):
    checked_address(address)
    return original_connect_ex(self, address)


def resolve(host, *args, **kwargs):
    if not local(host):
        raise socket.gaierror('Offline QA: external DNS blocked')
    return original_resolve(host, *args, **kwargs)


def sendto(self, data, *args):
    checked_address(args[-1])
    return original_sendto(self, data, *args)


socket.socket.connect = connect
socket.socket.connect_ex = connect_ex
socket.socket.sendto = sendto
socket.getaddrinfo = resolve
os.environ['PATIENT_SYNC_TOKEN'] = ''
os.environ['PATIENT_SYNC_TOKEN_FILE'] = '/nonexistent/offline-synthetic-only'
sys.argv = ['manage.py', 'test', *sys.argv[1:]]
sys.path.insert(0, os.getcwd())
runpy.run_path('manage.py', run_name='__main__')
