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
from registering import Registering

gettext.bindtextdomain('gooroom-client-server-register', '/usr/share/locale')
gettext.textdomain('gooroom-client-server-register')
_=gettext.gettext

class ShellRegistering(Registering):

    def __init__(self):
        Registering.__init__(self)

    def input_surely(self, prompt):
        user_input = ''
        while not user_input:
            user_input = input(prompt)

        return user_input

    def cli(self, client_data):
        'Get request info from keyboard using cli'

        #SARABAL VERSION REQUEST
        while True:
            cert_reg_type = self.input_surely(_('Enter certificate registration type[0:create 1:update 2: create or update]: '))
            if cert_reg_type != '0' and cert_reg_type != '1' and cert_reg_type != '2':
                continue
            break
        client_data['cert_reg_type'] = cert_reg_type

        #client_data['cn'] = self.input_surely(_('Enter the Client ID: '))
        client_data['cn'] = self.make_cn()

        if cert_reg_type == '1':
            client_data['name'] = ''
            client_data['ou'] = ''
        else:
            client_ip = self.make_ipname()
            client_data['name'] = \
                input(_('Enter the client name')+'[{}]: '.format(client_ip)) or client_ip
            client_data['ou'] = input(_('Enter the organizational unit: '))

        while True:
            api_type = self.input_surely(_('Enter the authentication type[0:id/password 1:regkey]: '))
            if api_type != '0' and api_type != '1':
                continue
            break

        if api_type == '0':
            api_type = 'id/pw'
            client_data['user_id'] = self.input_surely(_('Enter the gooroom admin ID: '))
            client_data['user_pw'] = getpass.getpass(_('Enter the password: '))
        else:
            api_type = 'regkey'
            client_data['regkey'] = self.input_surely(_('Enter the registration key: '))
        client_data['api_type'] = api_type

        client_data['password_system_type'] = "sha256"
        client_data['valid_date'] = input(_('(Option)Enter the valid date(YYYY-MM-DD): '))
        client_data['comment'] = input(_('(Option)Enter the comment: '))
        if self.ip_type == 'ipv4':
            client_data['ipv4'] = self.make_ipname()
            client_data['ipv6'] = ''
        else:
            client_data['ipv4'] = ''
            client_data['ipv6'] = self.make_ipv6name()
        return client_data

    def run(self, args):
        client_data = {}
        if args.cmd == 'cli':
            print(_('Gooroom Client Server Register.\n'))
            client_data['domain'] = self.input_surely(_('Enter the domain name: '))
            client_data['path'] = input(_('(Option)Enter the certificate path of gooroom root CA: '))

        elif args.cmd == 'noninteractive':
            client_data = {'domain':args.domain, 'path':args.CAfile}

        elif args.cmd == 'noninteractive-regkey':
            client_data = {'domain':args.domain, 'path':args.CAfile}

        server_certification = certification.ServerCertification()
        for ip_type in server_certification.get_root_certificate(client_data):
            self.ip_type=ip_type

        self.do_certificate(args, server_certification, client_data)

    def do_certificate(self, args, server_certification, client_data):
        """
        certificate
        """

        if args.cmd == 'cli':
            client_data = self.cli(client_data)
        elif args.cmd == 'noninteractive':
            client_data['cn'] = self.make_cn()
            client_data['name'] = args.name
            if args.unit:
                client_data['ou'] = args.unit
            else:
                client_data['ou'] = ''
            client_data['password_system_type'] = "sha256"
            client_data['user_id'] = args.id
            client_data['user_pw'] = args.password
            client_data['valid_date'] = args.expiration_date
            client_data['comment'] = args.comment
            client_data['api_type'] = 'id/pw'
            client_data['cert_reg_type'] = args.cert_reg_type
            if self.ip_type == 'ipv4':
                client_data['ipv4'] = self.make_ipname()
                client_data['ipv6'] = ''
            else:
                client_data['ipv4'] = ''
                client_data['ipv6'] = self.make_ipv6name()
        elif args.cmd == 'noninteractive-regkey':
            client_data['cn'] = self.make_cn()
            client_data['name'] = args.name
            if args.unit:
                client_data['ou'] = args.unit
            else:
                client_data['ou'] = ''
            client_data['password_system_type'] = "sha256"
            client_data['valid_date'] = args.expiration_date
            client_data['comment'] = args.comment
            client_data['regkey'] = args.regkey
            client_data['api_type'] = 'regkey'
            client_data['cert_reg_type'] = args.cert_reg_type
            if self.ip_type == 'ipv4':
                client_data['ipv4'] = self.make_ipname()
                client_data['ipv6'] = ''
            else:
                client_data['ipv4'] = ''
                client_data['ipv6'] = self.make_ipv6name()
        else:
            print('can not support mode({})'.format(args.cmd))
            return

        client_certification = certification.ClientCertification(client_data['domain'])
        cc = client_certification.certificate(client_data)
        for result in cc:
            result_text = self.result_format(result['log'])
            if result['err']:
                print("###########ERROR(%s)###########" % result['err'])
                print(result_text)
                exit(1)

            print(result_text)

    def make_name(self):
        """
        make name with hostname@ip
        """

        import socket
        return socket.gethostname()
