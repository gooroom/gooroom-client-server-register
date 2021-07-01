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
from gi.repository import Gdk, Gtk, GLib

import certification
import subprocess

from pwd import getpwnam
from registering import Registering
from register_define import *

gettext.install("gooroom-client-server-register", TRANSLATE_RES)

class RegisterThread(threading.Thread):
    def __init__(self, datas, application):
        threading.Thread.__init__(self)
        self.datas = datas
        self.application = application

    def make_result_view(self, result, errlog=None):
        result_image = self.application.builder.get_object('result_image')
        result_title = self.application.builder.get_object('result_title')
        result_detail = self.application.builder.get_object('result_detail')
        result_button = self.application.builder.get_object('result_button')

        result_detail.set_justify(Gtk.Justification.CENTER)
        text_mark = str("<span fgcolor='#0251ff'>%s</span>" % _("Administrator"))

        if result:
            result_button.get_style_context().add_class('accent_button')
            result_button.set_label(_('Finished'))
            result_button.connect('clicked', Gtk.main_quit)

            result_image.set_from_file(IMAGE_RES + 'image-success.svg')
            result_title.set_text(_("Client registration completed."))

            text_orig = str(_("Contact to Server Administrator for Detail Management."))
            text_chage = text_orig.replace(_("Administrator"), text_mark)
            result_detail.set_markup(text_chage)
        else:
            result_button.get_style_context().add_class('mono_button')
            result_button.set_label(_('Prev'))
            result_button.connect('clicked', self.application.prev_page)

            result_image.set_from_file(IMAGE_RES + 'image-failed.svg')
            result_title.set_text(_("Client registration failed."))
            if errlog:
                text_orig = str('{0}\n{1}'.format(errlog, _('Contact to Server Administrator for Resolution.')))
            else:
                text_orig = str(_('Contact to Server Administrator for Resolution.'))
            text_chage = text_orig.replace(_("Administrator"), text_mark)
            result_detail.set_markup(text_chage)

        register_stack = self.application.builder.get_object('register_stack')
        register_stack.set_visible_child_name('result_page')


    def run(self):
        errlog = str()
        try:
            client_data = next(self.datas)
            client_certification = certification.ClientCertification(client_data[DOMAIN])
            cc = client_certification.certificate(client_data)
            for client_result in cc:
                if client_result['err']:
                    errlog = str(client_result['log'][-2])
                    raise Exception
        except Exception as e:
            GLib.idle_add(self.make_result_view, False, errlog)
            print(type(e), e)
        else:
            GLib.idle_add(self.make_result_view, True)


class GUIRegistering(Registering):
    def __init__(self):
        Registering.__init__(self)

        cssProvider = Gtk.CssProvider()
        cssProvider.load_from_path(RESOURCES + 'style.scss')
        screen = Gdk.Screen.get_default()
        styleContext = Gtk.StyleContext()
        styleContext.add_provider_for_screen(screen, cssProvider, Gtk.STYLE_PROVIDER_PRIORITY_USER)

        glade_file = RESOURCES + "gooroomClientServerRegister.glade"

        self.builder = Gtk.Builder()
        self.builder.add_from_file(glade_file)

        self.window = self.builder.get_object('window1')
        self.window.set_default_size(510, 585)
        self.window.set_title(_('Gooroom Client Server Register'))
        self.window.set_icon_name('gooroom-client-server-register')
        self.window.set_position(Gtk.WindowPosition.CENTER)

        textview = self.builder.get_object('label_subtitle')
        textview.set_pixels_above_lines(2)
        textview.get_buffer().set_text(_("Register Gooroom Root CA in the client.\nAnd, add gooroom platform management servers from the server."))
        self.builder.get_object('label_cert_type').set_text(_('How to regist certificate'))
        self.builder.get_object('radiobutton_create').set_label(_('Create'))
        self.builder.get_object('radiobutton_create').connect('toggled', self.on_radiobutton_create_clicked)

        self.builder.get_object('radiobutton_update').set_label(_('Update'))
        self.builder.get_object('radiobutton_update').connect('toggled', self.on_radiobutton_create_clicked)

        self.builder.get_object('server_info_label').set_text(_('Server Information'))
        self.builder.get_object('checkbutton_hosts').set_label(_('Record in /etc/hosts'))
        self.builder.get_object('checkbutton_hosts').connect('toggled', self.on_checkbutton_hosts_toggled)
        list_box = self.builder.get_object('list_serverinfo')
        gkm_row = self.create_server_info_row(_('GKM'), _('Enter the domain name'))
        list_box.add(gkm_row)

        self.builder.get_object('select_cert_label').set_text(_('Select Certification'))
        self.builder.get_object('label_path').set_text(_('(Option)Select the certificate path of gooroom root CA'))
        self.builder.get_object('entry_file').set_text('')
        self.builder.get_object('button_browse').set_label(_('browse...'))
        self.builder.get_object('button_browse').connect('clicked', self.file_browse)

        self.builder.get_object('client_info_label').set_label(_('Client Information'))

        self.builder.get_object('register_info_label').set_label(_('Register Information'))
        self.on_radiobutton_create_clicked()

        self.builder.get_object('radiobutton_regkey').set_label(_('REGKEY'))
        self.builder.get_object('radiobutton_regkey').connect('toggled', self.on_radiobutton_regkey_clicked)
        list_box = self.builder.get_object('grid2')
        regkey_row = self.create_regi_info_row(REG_KEY, _('REGKEY'), _('Enter the registration key.'))
        list_box.add(regkey_row)

        self.builder.get_object('radiobutton_idpw').set_label(_('ID/PW'))
        self.builder.get_object('radiobutton_idpw').connect('toggled', self.on_radiobutton_idpw_clicked)

        self.builder.get_object('label_comment').set_text(_('(Option)Comment'))
        self.builder.get_object('comment_entry').set_placeholder_text(_('(Option)Enter the comment'))

        self.builder.get_object('button_close').set_label(_('Cancel'))
        self.builder.get_object('button_close').connect('clicked', Gtk.main_quit)
        self.builder.get_object('button_register').set_label(_('Register'))
        self.builder.get_object('button_register').connect('clicked', self.register)

        self.server_certification = certification.ServerCertification()

        self.window.connect("delete-event", Gtk.main_quit)
        self.window.show_all()


    def run(self):
        Gtk.main()


    def prev_page(self, button):
        scroll_window = self.builder.get_object('scroll_window')
        adjustment = scroll_window.get_vadjustment()
        adjustment.set_value(adjustment.get_lower())
        register_stack = self.builder.get_object('register_stack')
        register_stack.set_visible_child_name('register_page')


    def create_regi_info_row(self, name, label_text, placeholder_entry=None, entry_text=None, entry_sensitive=True, entry_purpose=None):
        box = Gtk.Box(orientation=1, spacing=10)
        box.set_margin_top(20)
        box.set_hexpand(True)
        box.set_name(name)

        label = Gtk.Label()
        label.set_text(label_text)
        label.set_xalign(0)
        label.get_style_context().add_class('Client_Label')
        
        entry = Gtk.Entry()
        entry.get_style_context().add_class('entry')
        if placeholder_entry:
            entry.set_placeholder_text(placeholder_entry)
        if entry_text:
            entry.set_text(entry_text)
        if not entry_sensitive:
            entry.set_sensitive(entry_sensitive)
        if entry_purpose:
            entry.set_input_purpose(entry_purpose)
            entry.set_visibility(False)

        box.pack_start(label, True, True, 0)
        box.pack_start(entry, True, True, 0)

        return box


    def on_radiobutton_create_clicked(self, obj=None):
        client_data_list = self.builder.get_object('client_data')

        for row in client_data_list.get_children():
            client_data_list.remove(row)

        create_button = self.builder.get_object('radiobutton_create')
        client_id_row = self.create_regi_info_row(CLIENT_ID, label_text=_('Client ID'), entry_text=self.make_cn(), entry_sensitive=False)

        client_data_list.add(client_id_row)

        if create_button.get_active():
            client_name_row = self.create_regi_info_row(CLIENT_NAME, _('Client name'), _('Enter the client name.'), self.make_ipname())
            client_classify_row = self.create_regi_info_row(CLIENT_UNIT, _('Client organizational unit'), _('Enter the organizational unit.'))

            client_data_list.add(client_name_row)
            client_data_list.add(client_classify_row)

        self.window.show_all()


    def on_radiobutton_idpw_clicked(self, obj):
        """
        """
        if not obj.get_active():
            return

        list_box = self.builder.get_object('grid2')

        for row in list_box.get_children():
            list_box.remove(row)

        id_row = self.create_regi_info_row(USER_ID, _('Gooroom admin ID'), _('Enter the gooroom admin ID.'))
        pw_row = self.create_regi_info_row(USER_PW, label_text=_('Password'), placeholder_entry=_('Enter the password.'), entry_purpose=Gtk.InputPurpose.PASSWORD)
        exp_row = self.create_regi_info_row(VALID_DATE, _('(Option)Certificate expiration date'), _('(Option)Enter the valid date(YYYY-MM-DD)'))

        list_box.add(id_row)
        list_box.add(pw_row)
        list_box.add(exp_row)

        self.window.show_all()


    def on_radiobutton_regkey_clicked(self, obj):
        """
        """
        if not obj.get_active():
            return

        list_box = self.builder.get_object('grid2')

        for row in list_box.get_children():
            list_box.remove(row)

        regkey_row = self.create_regi_info_row(REG_KEY, _('REGKEY'), _('Enter the registration key.'))

        list_box.add(regkey_row)

        self.window.show_all()


    def create_server_info_row(self, label_text, placeholder_domain, placeholder_ip=None, domain_edit=True):
        box = Gtk.Box(spacing=10)
        box.set_margin_top(10)
        box.set_hexpand(True)
        
        label = Gtk.Label()
        label.set_text(label_text)
        label.set_xalign(0)
        label.set_size_request(36, -1)
        label.get_style_context().add_class('Server_Label')

        domain = Gtk.Entry()
        domain.set_placeholder_text(placeholder_domain)
        domain.get_style_context().add_class('entry')
        if not domain_edit:
            domain.set_property('editable', False)
            domain.set_sensitive(False)

        box.pack_start(label, False, False, 0)
        box.pack_start(domain, True, True, 0)

        if placeholder_ip:
            ip = Gtk.Entry()
            ip.get_style_context().add_class('entry')
            ip.set_size_request(150, -1)
            ip.set_placeholder_text(placeholder_ip)
            box.pack_start(ip, False, True, 0)

        return box
        

    def on_checkbutton_hosts_toggled(self, obj):
        """
        toggle hosts checkbutton
        """

        list_box = self.builder.get_object('list_serverinfo')

        for row in list_box.get_children():
            list_box.remove(row)

        if obj.get_active():
            gkm_row = self.create_server_info_row(_('GKM'), _('Enter the domain name'), _('Enter ip address'))
            glm_row = self.create_server_info_row(_('GLM'), _('This domain is set on the GPMS'), _('Enter ip address'), False)
            grm_row = self.create_server_info_row(_('GRM'), _('This domain is set on the GPMS'), _('Enter ip address'), False)
            gpms_row = self.create_server_info_row(_('GPMS'), _('This domain is set on the GPMS'), _('Enter ip address'), False)

            list_box.add(gkm_row)
            list_box.add(glm_row)
            list_box.add(grm_row)
            list_box.add(gpms_row)

            self.window.show_all()
        else:
            gkm_row = self.create_server_info_row(_('GKM'), _('Enter the domain name'))
            list_box.add(gkm_row)

            self.window.show_all()


    def check_values(self):
        try:
            serverinfo = self.get_serverinfo()
        except Exception as error:
            print(type(error), error)

        if serverinfo[GKM][0] == '':
            self.show_info_dialog(_('Please enter the domain'))
            raise
        domain = serverinfo[GKM][0]

        checkbutton_hosts = self.builder.get_object('checkbutton_hosts')
        if checkbutton_hosts.get_active():
            if serverinfo[GKM][1] == '':
                self.show_info_dialog(_('GKM ip adress must be present'))
                raise

        path = self.builder.get_object('entry_file').get_text()

        server_certification = self.server_certification
        server_certification.add_hosts_gkm(serverinfo)

        try:
            for ip_type in server_certification.get_root_certificate({'domain':domain, 'path':path}):
                self.ip_type = ip_type
        except:
            self.show_info_dialog(_('Authentication server connection failed.\n'\
                                    'Check the connection information and network status.'))
            raise


    def catch_user_id(self):
        """
        get session login id
        (-) not login
        (+user) local user
        (user) remote user
        """

        pp = subprocess.Popen(
            ['loginctl', 'list-sessions'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        pp_out, pp_err = pp.communicate()
        pp_out = pp_out.decode('utf8').split('\n')

        for l in pp_out:
            l = l.split()
            if len(l) < 3:
                continue
            try:
                sn = l[0].strip()
                if not sn.isdigit():
                    continue
                uid = l[1].strip()
                if not uid.isdigit():
                    continue
                user = l[2].strip()
                pp2 = subprocess.Popen(
                    ['loginctl', 'show-session', sn],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE)

                pp2_out, pp2_err = pp2.communicate()
                pp2_out = pp2_out.decode('utf8').split('\n')
                service_lightdm = False
                state_active = False
                active_yes = False
                for l2 in pp2_out:
                    l2 = l2.split('=')
                    if len(l2) != 2:
                        continue
                    k, v = l2
                    k = k.strip()
                    v = v.strip()
                    if k == 'Id'and v != sn:
                        break
                    elif k == 'User'and v != uid:
                        break
                    elif k == 'Name' and v != user:
                        break
                    elif k == 'Service':
                        if v == 'lightdm':
                            service_lightdm = True
                        else:
                            break
                    elif k == 'State':
                        if v == 'active':
                            state_active = True
                        else:
                            break
                    elif k == 'Active':
                        if v == 'yes':
                            active_yes = True

                    if service_lightdm and state_active and active_yes:
                        gecos = getpwnam(user).pw_gecos.split(',')
                        if len(gecos) >= 5 and gecos[4] == 'gooroom-account':
                            return user
                        else:
                            return '+{}'.format(user)
            except:
                AgentLog.get_logger().debug(agent_format_exc())

        return '-'


    def file_browse(self, button):
        '''
        dialog = Gtk.FileChooserDialog(_('Select a certificate'), self.builder.get_object('window1'),
            Gtk.FileChooserAction.OPEN,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
             Gtk.STOCK_OPEN, Gtk.ResponseType.OK))

        self.add_filters(dialog)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self.builder.get_object('entry_file').set_text(dialog.get_filename())

        dialog.destroy()
        '''

        login_id = self.catch_user_id()
        if login_id[0] == '+':
            login_id = login_id[1:]
        fp = subprocess.check_output(
            ['sudo', 
            '-u', 
            login_id, 
            '/usr/lib/gooroom/gooroomClientServerRegister/file-chooser.py'])
        fp = fp.decode('utf8').strip()
        if fp and fp.startswith('path='):
            self.builder.get_object('entry_file').set_text(fp[5:])


    def add_filters(self, dialog):
        filter_text = Gtk.FileFilter()
        filter_text.set_name(_("Certificate files"))
        filter_text.add_mime_type("application/x-x509-ca-cert")
        dialog.add_filter(filter_text)

        filter_any = Gtk.FileFilter()
        filter_any.set_name(_("Any files"))
        filter_any.add_pattern("*")
        dialog.add_filter(filter_any)


    def register(self, button):
        try:
            self.check_values()
        except:
            return

        datas = self.get_datas()
        register_thread = RegisterThread(datas, self)
        register_thread.start()


    def get_serverinfo(self):
        """
        get domain/ip of gkm/glm/grm/gpms for writing to /etc/hosts
        """

        hosts_data = {}

        serverinfo = self.builder.get_object('list_serverinfo')
        for info in serverinfo.get_children():
            items = info.get_children()
            label = items[0].get_text()
            domain = items[1].get_text()
            ip = ''

            if len(items) > 2:
                ip = items[2].get_text()

            hosts_data[label.lower()] = (domain, ip)

        return hosts_data


    def get_registerinfo(self):
        register_data = {USER_ID:'', USER_PW:'', VALID_DATE:'', REG_KEY:''}
        registerinfo = self.builder.get_object('grid2')

        if self.builder.get_object('radiobutton_idpw').get_active():
            register_data[API_TYPE] = 'id/pw'
        else:
            register_data[API_TYPE] = 'regkey'

        for info in registerinfo.get_children():
            name = info.get_name()
            items = info.get_children()
            value = items[1].get_text()
            register_data[name] = value

        return register_data


    def get_clientinfo(self):
        client_data = {CLIENT_ID:'', CLIENT_NAME:'', CLIENT_UNIT:''}

        client_data_list = self.builder.get_object('client_data')
        for data in client_data_list.get_children():
            name = data.get_name()
            items = data.get_children()
            value = items[1].get_text()
            client_data[name] = value

        return client_data


    def get_datas(self):
        "Return input information"
        client_data = {}

        serverinfo = self.get_serverinfo()
        client_data['serverinfo'] = serverinfo
        client_data[DOMAIN] = serverinfo[GKM][0]
        client_data[CERT_PATH] = self.builder.get_object('entry_file').get_text()

        cn_datas = self.get_clientinfo()
        client_data[CLIENT_ID] = cn_datas[CLIENT_ID]
        client_data[CLIENT_NAME] = cn_datas[CLIENT_NAME]
        client_data[CLIENT_UNIT] = cn_datas[CLIENT_UNIT]

        register_data = self.get_registerinfo()
        client_data[PW_TYPE] = "sha256"
        client_data[API_TYPE] = register_data[API_TYPE]
        client_data[USER_ID] = register_data[USER_ID]
        client_data[USER_PW] = register_data[USER_PW]
        client_data[VALID_DATE] = register_data[VALID_DATE]
        client_data[REG_KEY] = register_data[REG_KEY] 

        client_data[COMMENT] = self.builder.get_object('comment_entry').get_text()

        if self.builder.get_object('radiobutton_create').get_active():
            cert_reg_type = '0'
        elif self.builder.get_object('radiobutton_update').get_active():
            cert_reg_type = '1'
        else:
            cert_reg_type = '2'
        client_data[CERT_REG_TYPE] = cert_reg_type

        if self.ip_type == IPV4:
            client_data[IPV4] = self.make_ipname()
            client_data[IPV6] = ''
        else:
            client_data[IPV4] = ''
            client_data[IPV6] = self.make_ipv6name()
        
        yield client_data


    def show_info_dialog(self, message, error=None):
        dialog = Gtk.MessageDialog(self.builder.get_object('window1'), 0,
            Gtk.MessageType.INFO, Gtk.ButtonsType.OK, 'info dialog')
        dialog.set_title(_('Gooroom Management Server Registration'))
        dialog.format_secondary_text(message)
        dialog.set_icon_name('gooroom-client-server-register')
        dialog.props.text = error
        response = dialog.run()
        if response == Gtk.ResponseType.OK or response == Gtk.ResponseType.CLOSE:
            dialog.destroy()

