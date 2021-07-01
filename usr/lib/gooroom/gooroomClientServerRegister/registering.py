#!/usr/bin/python3
import gettext
import os
import getpass
import pprint
import threading
import time
import copy
import hashlib
import codecs

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, Gtk

import certification
import subprocess

from pwd import getpwnam

gettext.install("gooroom-client-server-register", "/usr/share/locale")

class Registering():
    "Registering parent class"
    def __init__(self):
        self.WORK_DIR = '/usr/lib/gooroom/gooroomClientServerRegister'

    def result_format(self, result):
        "Return result log pretty"
        # TODO: formatting more pretty
        result_text = ''
        for text in result:
            result_text += pprint.pformat(text) + '\n'

        return result_text

    def make_hash_cn(self):
        cmd = subprocess.run(['/usr/sbin/dmidecode', '-s', 'system-serial-number'], stdout=subprocess.PIPE, universal_newlines=True)
        result = cmd.stdout.rstrip() + '/'
        cmd = subprocess.run(['/usr/sbin/dmidecode', '-s', 'system-uuid'], stdout=subprocess.PIPE, universal_newlines=True)
        result += cmd.stdout.rstrip() + '/'
        cmd = subprocess.run(['/usr/sbin/dmidecode', '-s', 'baseboard-serial-number'], stdout=subprocess.PIPE, universal_newlines=True)
        result += cmd.stdout.rstrip()
        hash_result = hashlib.md5(result.encode()).hexdigest()
        base64_result = codecs.encode(codecs.decode(hash_result, 'hex'), 'base64').decode().rstrip()
        return base64_result

    def make_mac(self):
        """
        make cn with sn + mac
        """

        ENP_PATH = '/sys/class/net/enp0s3/address'
        if os.path.exists(ENP_PATH):
            with open(ENP_PATH) as f:
                cn = f.read().strip('\n').replace(':', '')
                print('enp0s3={}'.format(cn))
                return cn
        else:
            import glob
            ifaces = [i for i in glob.glob('/sys/class/net/*')]
            ifaces.sort()
            for iface in ifaces:
                if iface == '/sys/class/net/lo':
                    continue
                with open(iface+'/address') as f2:
                    cn = f2.read().strip('\n').replace(':', '')
                    print('iface={}'.format(cn))
                    return cn
            return 'CN-NOT-FOUND-ERROR'

    def make_cn(self):

        CN_PATH = '/etc/gooroom/gooroom-client-server-register/gcsr.conf'
        if os.path.exists(CN_PATH):
            try:
                import configparser
                parser = configparser.RawConfigParser()
                parser.optionxform = str
                parser.read(CN_PATH)
                cn = parser.get('certificate', 'client_name').strip().strip('\n')
                print('gcsr.conf={}'.format(cn))
                return cn
            except:
                pass

        cn = self.make_mac()
        return cn + self.make_hash_cn()

    def make_ipname(self):
        """
        make name with IP
        """
        return os.popen('hostname --all-ip-addresses').read().split(' ')[0]

    def make_ipv6name(self):
        """
        make name with IPv6
        """
        return os.popen('/sbin/ip -6 addr | grep inet6 | awk -F \'[ \t]+|/\' \'{print $3}\' | grep -v ^::1').read().split('\n')[0]


