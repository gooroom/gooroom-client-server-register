#!/usr/bin/python3
"""OpenSSL related object required to obtaion a certificate from the gooroom managerment server.
Written by python3
Make RSA 2048 client key pair and save key pair.
Make csr and singing from client private key and save csr.`
"""
import configparser
import gettext
import grp
import hashlib
import os
import shutil
import socket
import subprocess
import time
from datetime import datetime

import OpenSSL
import requests

import urllib3
urllib3.disable_warnings(urllib3.exceptions.SecurityWarning)

gettext.install('gooroom-client-server-register', '/usr/share/locale')

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk

import ctypes
import json
LSF_CRYPTO_LIB_PATH = '/usr/lib/x86_64-linux-gnu/liblsf-crypto.so'
LSF_RSA_PUBLICKEY_TYPE = 0
LSF_RSA_PRIVATEKEY_TYPE = 1

LSF_CRYPTO_SUCCESS = 0
LSF_CRYPTO_FAIL = 1

LSF_CRYPTO_ERRSG_LEN = 256

#-----------------------------------------------------------------------
class LSF_ERROR_T(ctypes.Structure):
    _fields_ = [('message', ctypes.c_char * LSF_CRYPTO_ERRSG_LEN)]

#-----------------------------------------------------------------------

def get_api():
    """
    get liblsf.so instance
    """

    if not get_api.api:
        get_api.api = ctypes.CDLL(LSF_CRYPTO_LIB_PATH)
    return get_api.api

get_api.api = None

class Certification():
    def __init__(self):
        self.server_key = '/etc/ssl/private/gooroom_server.key'
        self.result = {'err':None, 'log':[]}
        self.config_dir = '/etc/gooroom/gooroom-client-server-register'
        self.config_file = os.path.join(self.config_dir, 'gcsr.conf')
        self.client_key = '/etc/ssl/private/gooroom_client.key'
        self.kcmvp_on_off = 'off'

    def check_data(self):
        "Checking the input data is correct"
        raise NotImplementedError('Implement check data method.')

    def certificate(self):
        "do certificate"
        raise NotImplementedError("Implement certificate method.")

    @staticmethod
    def remove_file(path):
        "remove file if existss"
        if os.path.exists(path):
            os.remove(path)

    def response(self, res):
        """data is response from server
        response type is json type, if not raise error.
        convert to dictionay, then return data"""
        if res.status_code == 200:
            return res.json()
        else:
            raise ResponseError('Status Code:[{0}], {1}'.format(res.status_code, res.text))

    def _save_config(self, section, section_data):
        "Save config file. Section is config section name, section_data is dictionary of section."
        if not os.path.isdir(self.config_dir):
            os.makedirs(self.config_dir)

        config = configparser.ConfigParser()
        config.read(self.config_file)

        config[section] = section_data
        with open(self.config_file, 'w') as conf_file:
            config.write(conf_file)

    def _save_key(self, key, fullpath):
        """save key and change owner.
        Return ssl privite path
        """
        ssl_cert_gid = grp.getgrnam('ssl-cert').gr_gid

        with open(fullpath, 'wb') as key_file:
            key_file.write(key)

        shutil.chown(fullpath, group=ssl_cert_gid)
        os.chmod(fullpath, 0o640)

    def _read_hosts_except_gen(self):
        """
        read /etc/hosts except generating by gcsr
        """

        with open('/etc/hosts', 'r') as f:
            lines = f.readlines()

        hosts = ''
        parsing = True
        for line in lines:
            if line == '### Auto Generated by gcsr\n':
                parsing = False
            elif line.endswith('End gcsr\n'):
                parsing = True
                continue
            elif line.strip() == '':
                continue

            if parsing:
                hosts += line

        return hosts

    def lsf_decode(self, target):
        api = get_api()
        crypto_error = ctypes.POINTER(LSF_ERROR_T)()
        b64_decoded = ctypes.POINTER(ctypes.c_ubyte)()
        b64_decoded_len = ctypes.c_int()
        r = api.lsf_base64_decode(
                                target.encode('utf-8'),
                                len(target),
                                ctypes.byref(b64_decoded),
                                ctypes.byref(b64_decoded_len),
                                ctypes.byref(crypto_error) #or None
                                )
        if r != LSF_CRYPTO_SUCCESS:
            print('error={}'.format(crypto_error.contents.message))
            return


        rsa_decoded_private_key = ctypes.POINTER(ctypes.c_ubyte)()
        rsa_decoded_private_key_len = ctypes.c_int()
        r = api.lsf_read_key_MC_RSA_PKCS1(
                        self.client_key.encode('utf-8'),
                        LSF_RSA_PRIVATEKEY_TYPE,
                        ctypes.byref(rsa_decoded_private_key),
                        ctypes.byref(rsa_decoded_private_key_len),
                        ctypes.byref(crypto_error) #or None
                        )
        if r != LSF_CRYPTO_SUCCESS:
            print('error={}'.format(crypto_error.contents.message))
            return

        result = ""
        num = 0
        while num < b64_decoded_len.value :
            rsa_decrypted_text = ctypes.POINTER(ctypes.c_ubyte)() #ctypes.c_char_p()
            rsa_decrypted_text_len = ctypes.c_int()
            r = api.lsf_decrypt_MC_RSAOAEP_SHA256(
                                        rsa_decoded_private_key,
                                        rsa_decoded_private_key_len,
                                        ctypes.cast(b64_decoded, ctypes.POINTER(ctypes.c_char))[num:num+256],
                                        ctypes.c_int(256),
                                        ctypes.byref(rsa_decrypted_text),
                                        ctypes.byref(rsa_decrypted_text_len),
                                        ctypes.byref(crypto_error) #or None
                                        )
            num += 256
            if r != LSF_CRYPTO_SUCCESS:
                print('error={}'.format(crypto_error.contents.message))
                return

            result += format(ctypes.cast(rsa_decrypted_text, ctypes.c_char_p).value.decode('utf-8'))
        return result

    def lsf_encode(self, target):
        rsa_decoded_public_key = ctypes.POINTER(ctypes.c_ubyte)()
        rsa_decoded_public_key_len = ctypes.c_int()

        api = get_api()
        crypto_error = ctypes.POINTER(LSF_ERROR_T)()

        rsa_decoded_public_key = ctypes.POINTER(ctypes.c_ubyte)()
        rsa_decoded_public_key_len = ctypes.c_int()
        r = api.lsf_read_key_MC_RSA_PKCS1(
                        self.server_key.encode('utf-8'),
                        LSF_RSA_PUBLICKEY_TYPE,
                        ctypes.byref(rsa_decoded_public_key),
                        ctypes.byref(rsa_decoded_public_key_len),
                        ctypes.byref(crypto_error) #or None
                        )

        if r != LSF_CRYPTO_SUCCESS:
            print('error={}'.format(crypto_error.contents.message))
            return

        start = 0
        rsa_encrypted_full_text = []#ctypes.POINTER(ctypes.c_ubyte)()
        rsa_encrypted_full_text_len = ctypes.c_int()
        while len(target) > start:
            if (len(target)-start)/190 == 0 :
                end = start + len(target)
            else :
                end = start + 190
            rsa_encrypted_text = ctypes.POINTER(ctypes.c_ubyte)()
            rsa_encrypted_text_len = ctypes.c_int()
            r = api.lsf_encrypt_MC_RSAOAEP_SHA256(
                                        rsa_decoded_public_key,
                                        rsa_decoded_public_key_len,
                                        target.encode('utf-8')[start:end],
                                        ctypes.byref(rsa_encrypted_text),
                                        ctypes.byref(rsa_encrypted_text_len),
                                        ctypes.byref(crypto_error) #or None
                                        )
            if r != LSF_CRYPTO_SUCCESS:
                print('error={}'.format(crypto_error.contents.message))
                return
            rsa_encrypted_full_text[int(start/190*256) : int((start/190*256) + 256)] += rsa_encrypted_text[:256]
            start += 190
            rsa_encrypted_full_text_len.value += rsa_encrypted_text_len.value

        b64_encoded = ctypes.POINTER(ctypes.c_ubyte)()
        b64_encoded_len = ctypes.c_int()
        r = api.lsf_base64_encode(
                                bytes(rsa_encrypted_full_text),
                                rsa_encrypted_full_text_len,
                                ctypes.byref(b64_encoded),
                                ctypes.byref(b64_encoded_len),
                                ctypes.byref(crypto_error) #or None
                                )
        if r != LSF_CRYPTO_SUCCESS:
            print('error={}'.format(crypto_error.contents.message))
            return

        return format(ctypes.cast(b64_encoded, ctypes.c_char_p).value.decode('utf-8'))



class ServerCertification(Certification):

    def __init__(self):
        Certification.__init__(self)
        self.root_crt_path = '/usr/local/share/ca-certificates/gooroom_root.crt'
        self.err_msg = _('Fail to register Gooroom Platform Management Server complete.')

    def get_root_certificate(self, data):
        """data['path'] distinguish how to get the root certificate.
         True: get root certificate from local.
        False : get root certificate from server certificate chain."""
        domain = data['domain']
        local_crt_path = data['path']

        # get root certificate from gooroom key server certificate chain
        if ':' in domain:
            port = int(domain.strip('\n').split(':')[-1])
        else:
            port = 443

        addrinfo = socket.getaddrinfo(domain, port, 0, 0, socket.SOL_TCP)

        if addrinfo[0][0] == socket.AF_INET: #IPv4
            ipver = socket.AF_INET
            yield "ipv4"
        else:
            ipver = socket.AF_INET6
            yield "ipv6"

        if local_crt_path:
            # get root certificate from local path
            # TODO: need to verify certificate
            if local_crt_path != self.root_crt_path:
                self.remove_file(self.root_crt_path)
                shutil.copy(local_crt_path, self.root_crt_path)
        else:
            s = socket.socket(ipver, socket.SOCK_STREAM, 0)
            s.settimeout(5)
            s.connect((domain, port))

            ssl_context = OpenSSL.SSL.Context(OpenSSL.SSL.TLSv1_2_METHOD)
            ssl_conn = OpenSSL.SSL.Connection(ssl_context, s)
            ssl_conn.set_connect_state()
            ssl_conn.set_tlsext_host_name(bytes(domain.encode('utf-8')))
            tries = 0
            while True:
                try:
                    ssl_conn.do_handshake()
                    break
                except OpenSSL.SSL.WantReadError:
                    tries += 1
                    if tries >= 5:
                        raise
                    time.sleep(0.1)

            certs = ssl_conn.get_peer_cert_chain()
            server_crt = ssl_conn.get_peer_certificate()
            server_crt = OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_PEM, server_crt)
            x509 = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, server_crt)
            pubkey = x509.get_pubkey()
            pubkeys = OpenSSL.crypto.dump_publickey(OpenSSL.crypto.FILETYPE_PEM,pubkey)
            self._save_key(pubkeys, self.server_key)

            # TODO: register all key chain
            root_crt = OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_PEM, certs[-1])
            if os.path.exists(self.root_crt_path):
                with open(self.root_crt_path) as f0:
                    old_crt = f0.read()
                    if old_crt == root_crt.decode('utf8'):
                        return

            self.remove_file(self.root_crt_path)

            with open(self.root_crt_path, 'wb') as f:
                f.write(root_crt)

        self._update_ca_certificate()

    def _update_ca_certificate(self):
        """address is (domain or IP) or certificate path
        seperated by server_crt_flag
        """
        update = ['update-ca-certificates', '--fresh']
        subprocess.check_output(update, shell=False)

    def add_hosts_gkm(self, serverinfo):
        """
        add gkm info to /etc/hosts
        """

        ######write gkm on /etc/hosts
        hosts = self._read_hosts_except_gen()

        if serverinfo:
            hosts += '\n### Auto Generated by gcsr\n'
            hosts += '{0}\t{1}\n'.format(serverinfo['gkm'][1], serverinfo['gkm'][0])
            hosts += '### Modify {} End gcsr\n'.format('temp')

        with open('/etc/hosts', 'w') as f:
            f.write(hosts)

class ClientCertification(Certification):

    def __init__(self, domain):
        Certification.__init__(self)
        self.domain = domain
        self.client_crt = '/etc/ssl/certs/gooroom_client.crt'
        self.public_key_path = '/etc/ssl/private/gooroom_public.key'

    def check_data(self, data, api_type):
        self.result['log'].append(_('Requesting client certificate.'))

        if not data['cert_reg_type'] \
            or data['cert_reg_type'] != '0' \
            and data['cert_reg_type'] != '1' \
            and data['cert_reg_type'] != '2':
            self.result['err'] = '101'
            self.result['log'].append(_('Check the cert-reg-type.'))
        elif not data['cn']:
            self.result['err'] = '101'
            self.result['log'].append(_('Check the client name.'))
        elif api_type == 'id/pw' and not data['user_id']:
            self.result['err'] = '101'
            self.result['log'].append(_('Check the gooroom admin ID.'))
        elif api_type == 'id/pw' and not data['user_pw']:
            self.result['err'] = '101'
            self.result['log'].append(_('Check the password.'))
        elif data['valid_date']:
            try:
                dt = datetime.strptime(data['valid_date'], '%Y-%m-%d')
                nt = datetime.now()
                nt = datetime(nt.year, nt.month, nt.day)

                delta = dt - nt
                if delta.days < 0:
                    self.result['err'] = '101'
                    self.result['log'].append(_('The expiration period of the '\
                                        'certificate can be set from today.'))
            except ValueError:
                self.result['err'] = '101'
                self.result['log'].append(_('Incorrect date format, should be YYYY-MM-DD'))

    def hash_password(self, **kargs):
        """
        Password hash algorithms are required depending on the settings of gpms.
        Argument: kargs(password, salt, etc...)

        Return: hashed password(str)
        """
        hash_tmp = hashlib.sha256(kargs['password'].encode()).hexdigest()

        return hashlib.sha256((kargs['id']+hash_tmp).encode()).hexdigest()

    def certificate(self, data):
        api_type = data['api_type']

        self.check_data(data, api_type)
        yield self.result

        #self.remove_file(self.client_key)
        csr, private_key, public_key = self.generate_csr(data['cn'], data['ou'])
        data['csr'] = csr

        url = ''
        cert_reg_type = data['cert_reg_type']
        if api_type == 'id/pw':
            if cert_reg_type == '0':
                url = 'https://%s/gkm/v1/client/register/idpw/create' % self.domain
            elif cert_reg_type == '1':
                url = 'https://%s/gkm/v1/client/register/idpw/update' % self.domain
            else:
                url = 'https://%s/gkm/v1/client/register/idpw/create_or_update' % self.domain
            data['user_pw'] = self.hash_password(id=data['user_id'],
                                                 password=data['user_pw'])
        elif api_type == 'regkey':
            if cert_reg_type == '0':
                url = 'https://%s/gkm/v1/client/register/regkey/create' % self.domain
            elif cert_reg_type == '1':
                url = 'https://%s/gkm/v1/client/register/regkey/update' % self.domain
            else:
                url = 'https://%s/gkm/v1/client/register/regkey/create_or_update' % self.domain

        self.result['log'] = []

        serverinfo = {}
        if 'serverinfo' in data:
            si = data['serverinfo']
            import copy
            serverinfo = copy.deepcopy(si)
            del si

        try:
            req_data = data
            get_header_url = 'https://%s/gkm/v1/gpms' % data['domain']
            res = requests.get(url=get_header_url, timeout=5)
            if 'MyHeader' in res.headers:
                self.kcmvp_on_off = 'on' if res.headers['MyHeader']=='kcmvpon' else 'off'
            if self.kcmvp_on_off == 'on':
                req_data['csr'] = req_data['csr'].decode('utf8')
                req_data = self.jsonParsing(req_data)
                req_data = json.dumps(req_data)
        except Exception as error:
            print("failed: get header")

        try:
            print(req_data)
            res = requests.post(url, data=req_data, timeout=30)
            response_data = self.response(res)
            # save crt
            self._save_key(private_key, self.client_key)
            self._save_key(public_key, self.public_key_path)
            if self.kcmvp_on_off == 'on':
                response_data = self.lsf_decode(response_data['encMessage'])
                response_data = json.loads(response_data)
            if response_data['status']['result'] != 'success':
                # fail to get data
                raise ResponseError('Result code:[{0}], {1}'.format(response_data['status']['resultCode'], response_data['status']['message']))

            with open(self.client_crt, 'w') as f:
                f.write(response_data['data'][0]['certInfo'])
                del response_data['data'][0]['certInfo']

            #del private_key

            self.result['log'].append(response_data['status']['message'])
            self.result['log'].append(response_data['data'][0])
            self._add_hosts(data, serverinfo)
            self.result['log'].append(_('List of Gooroom platform management server registration completed.'))
        except ResponseError as error:
            self.result['err'] = '104'
            self.result['log'].append(_('Client certificate issue failed.'))
            self.result['log'].append((type(error), error))
        except Exception as error:
            self.result['err'] = '105'
            self.result['log'].append(_('Server response type is wrong. Contact your server administrator.'))
            self.result['log'].append((type(error), error))
        else:
            self._save_config('certificate', self.get_certificate_data(data['cn'], data['ou'], data['password_system_type']))
            self.result['log'].append(_('Client registration completed.'))

        yield self.result

    def jsonParsing(self, data):
        scheme = '{"encMessage" : {}}'
        scheme = json.loads(scheme)
        data = json.dumps(data)
        scheme['encMessage'] = self.lsf_encode(data)
        return scheme

    def _add_hosts(self, data, serverinfo):
        """Get server list and /etc/hosts file from server.
        write /etc/hosts
        write config"""

        domain = data['domain']
        url = 'https://%s/gkm/v1/gpms' %  domain
        if self.kcmvp_on_off == 'on':
            cn = data['cn']
            cn = self.lsf_encode(cn)
            cn = json.dumps(cn)
            from urllib import parse
            cn = parse.quote(cn)
            #####request glm/grm/gpms infos
            url = 'https://%s/gkm/v1/gpms?encMessage=%s' % (domain, cn)
            res = requests.get(url, timeout=5)
            response_data = self.response(res)
            response_data = self.lsf_decode(response_data['encMessage'])
            response_data = json.loads(response_data)
        else:
            res = requests.get(url, timeout=5)
            response_data = self.response(res)

        if response_data['status']['result'] != 'success':
            # fail to get data
            raise ResponseError('Result code:[{0}], {1}'.format(response_data['status']['resultCode'], response_data['status']['message']))

        gpms = response_data['data'][0]

        modify_date = int(gpms['modifyDate']) / 1000
        modify_date = datetime.strftime(datetime.utcfromtimestamp(modify_date),
            ' %Y-%m-%d %H:%M:%S')

        #####write config
        gpms['gkmUrl'] = domain
        self._add_config(gpms)

        #####write gkm/glm/grm/gpms on /etc/hosts (again)
        hosts = self._read_hosts_except_gen()
        if serverinfo:
            hosts = self._read_hosts_except_gen()
            hosts += '\n### Auto Generated by gcsr\n'
            #add gkm
            hosts += '{0}\t{1}\n'.format(serverinfo['gkm'][1], serverinfo['gkm'][0])

            server_urls = [x for x in gpms if x.endswith('Url')]
            for server_url in server_urls:
                server_name = server_url.replace('Url', '')
                #skip gkm because of writing above(gkm data from gpms is empty )
                if server_name == 'gkm':
                    continue
                #add glm/grm/gpms
                server_ip = serverinfo[server_name][1]
                if server_ip:
                    hosts += '{0}\t{1}\n'.format(server_ip, gpms[server_url])
            hosts += '### Modify {} End gcsr\n'.format(modify_date)

            with open('/etc/hosts', 'w') as f:
                f.write(hosts)

    def _add_config(self, gpms):
        """
        write config
        """

        domain_datas = {}
        server_urls = [x for x in gpms if x.endswith('Url')]
        for server_url in server_urls:
            server_name = server_url.replace('Url', '')
            domain_datas[server_name] = gpms[server_url]

        self._save_config(section='domain', section_data=domain_datas)

    def __generate_key(self):
        """Generate key using gooroom client rsa/2048 key pair"""

        if not os.path.exists(self.public_key_path):
            key = OpenSSL.crypto.PKey()
            key.generate_key(OpenSSL.crypto.TYPE_RSA, 2048)

            private_key = OpenSSL.crypto.dump_privatekey(
                OpenSSL.crypto.FILETYPE_PEM, key)
            public_key = OpenSSL.crypto.dump_publickey(
                OpenSSL.crypto.FILETYPE_PEM, key)
            self._save_key(private_key, self.client_key)
            obj_private_key = obj_public_key = key
        else:
            with open(self.public_key_path) as f:
                public_key = f.read().encode('utf8')
                obj_public_key = OpenSSL.crypto.load_publickey(OpenSSL.crypto.FILETYPE_PEM, public_key)
            with open(self.client_key) as f2:
                private_key = f2.read().encode('utf8')
                obj_private_key = OpenSSL.crypto.load_privatekey(OpenSSL.crypto.FILETYPE_PEM, private_key)

        return obj_private_key, private_key, public_key, obj_public_key

    def generate_csr(self, common_name, organizational_unit):
        req = OpenSSL.crypto.X509Req()
        req.get_subject().CN = common_name
        if organizational_unit:
            req.get_subject().OU = organizational_unit

        obj_private_key, private_key, public_key, obj_public_key  = self.__generate_key()
        req.set_pubkey(obj_public_key)
        req.sign(obj_private_key, 'sha256')
        #del key

        csr = OpenSSL.crypto.dump_certificate_request(OpenSSL.crypto.FILETYPE_PEM, req)
        # Do not save csr
        return csr, private_key, public_key

    def get_certificate_data(self, client_name, organizational_unit, password_system_type):
        "Return certificate section data of gcsr.config"
        sc = ServerCertification()
        certificate_data = {'organizational_unit':organizational_unit,
            'password_system_type':password_system_type.lower(),
            'client_crt':self.client_crt,
            'client_name':client_name,
            'server_crt':sc.root_crt_path,
			'kcmvp_on_off':self.kcmvp_on_off}

        return certificate_data

class ResponseError(Exception):
    pass
