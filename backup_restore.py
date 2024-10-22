#!/usr/bin/env python

import argparse
import getpass
import json
from fnmatch import fnmatch

import requests
import urllib3
from avi.sdk.avi_api import ApiSession


class BackupRestore:
    def __init__(self, api, filename, passphrase, tenant='*', confirm=False):

        self.api = api
        self.filename = filename
        self.passphrase = passphrase
        self.confirm = confirm
        self.tenant = tenant

    @staticmethod
    def choice():
        while True:
            choice = input('[y/n]? ')
            if choice and 'yes'.startswith(choice):
                return True
            if choice and 'no'.startswith(choice):
                return False

    def backup(self, vs_match, include_certs=False):
        vs_matched = {}

        print('Looking for matching Virtual Services...')

        vs_list = self.api.get_objects_iter('virtualservice',
                                            params={'fields':
                                                    'name,uuid,tenant_ref',
                                                    'include_name': 'true'},
                                            tenant=tenant)

        for vs in vs_list:
            vs_name = vs['name']
            if fnmatch(vs_name, vs_match):
                tenant_name = vs['tenant_ref'].split('#')[1]
                vs_matched[(tenant_name, vs_name)] = vs['uuid']
                print(vs_name, end='')
                if self.tenant == '*':
                    print(f'@{tenant_name}', end='')
                print(end=' ')

        if not vs_matched:
            print('\r\nNo matching Virtual Services found.')
            return

        if self.confirm:
            print(f'\r\nConfirm backing up these '
                  f'{len(vs_matched)} Virtual Services?', end=' ')
            if not self.choice():
                return

        print()

        backup_data = {}

        for (tenant_name, vs_name), vs_uuid in vs_matched.items():
            print(f'Backing up {vs_name}')
            uri = f'configuration/export/virtualservice/{vs_uuid}'
            params = {'include_certs': include_certs,
                      'passphrase': self.passphrase}
            rsp = self.api.get(uri, params=params)
            if rsp.status_code >= 300:
                raise Exception(f'Error backing up {vs_name}: {rsp.text}')
            if tenant_name not in backup_data:
                backup_data[tenant_name] = {}
            backup_data[tenant_name][vs_name] = rsp.json()

        with open(self.filename, 'w') as backup_file:
            backup_file.write(json.dumps(backup_data))

        print('Backup complete.')

    def restore(self, vs_match):
        with open(self.filename, 'r') as backup_file:
            backup_data = json.loads(backup_file.read())

        vs_matched = {}

        print('Looking for matching Virtual Services...')

        for tenant_name, vs in backup_data.items():
            if self.tenant in ('*', tenant_name):
                for vs_name, backup in vs.items():
                    if fnmatch(vs_name, vs_match):
                        vs_matched[(tenant_name, vs_name)] = backup
                        print(vs_name, end='')
                        if self.tenant == '*':
                            print(f'@{tenant_name}', end='')

        if not vs_matched:
            print('\r\nNo matching Virtual Services found.')
            return

        if self.confirm:
            print('\r\nConfirm restoring these Virtual Services?', end=' ')
            if not self.choice():
                return

        print()

        for (tenant_name, vs_name), backup in vs_matched.items():
            print(f'Restoring {vs_name}')
            uri = 'configuration/import'
            data = {'passphrase': self.passphrase,
                    'configuration': backup}
            rsp = self.api.post(uri, data=data, tenant=tenant_name)
            if rsp.status_code >= 300:
                raise Exception(f'Error restoring {vs_name}: {rsp.text}')

# Disable certificate warnings


if hasattr(requests.packages.urllib3, 'disable_warnings'):
    requests.packages.urllib3.disable_warnings()

if hasattr(urllib3, 'disable_warnings'):
    urllib3.disable_warnings()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('operation', choices=('backup', 'restore'))
    parser.add_argument('filename', help='Backup filename')
    parser.add_argument('-e', '--passphrase', help='Encryption passphrase')
    parser.add_argument('-c', '--controller',
                        help='FQDN or IP address of Avi Controller')
    parser.add_argument('-u', '--user', help='Avi API Username',
                        default='admin')
    parser.add_argument('-p', '--password', help='Avi API Password')
    parser.add_argument('-t', '--tenant', help='Tenant',
                        default='admin')
    parser.add_argument('-x', '--apiversion', help='Avi API version')
    parser.add_argument('-v', '--vs', help='Virtual Service name or glob',
                        default='*')
    parser.add_argument('-i', '--include_certs', help='Include certificates in '
                        'the backup', action='store_true')
    parser.add_argument('-n', '--noconfirm', help='Do not ask to confirm '
                        'operation', action='store_true')

    args = parser.parse_args()

    if args:
        # If not specified on the command-line, prompt the user for the
        # controller IP address and/or password

        controller = args.controller
        user = args.user
        password = args.password
        tenant = args.tenant
        api_version = args.apiversion
        vs_match = args.vs
        operation = args.operation
        filename = args.filename
        passphrase = args.passphrase
        include_certs = args.include_certs
        confirm = not (args.noconfirm)

        while not controller:
            controller = input('Controller:')

        while not password:
            password = getpass.getpass(f'Password for {user}@{controller}:')

        if not api_version:
            # Discover Controller's version if no API version specified

            api = ApiSession.get_session(controller, user, password)
            api_version = api.remote_api_version['Version']
            api.delete_session()
            print(f'Discovered Controller version {api_version}.')
        api = ApiSession.get_session(controller, user, password,
                                     api_version=api_version)

        br = BackupRestore(api, filename, passphrase,
                           tenant=tenant, confirm=confirm)

        if operation == 'backup':
            br.backup(vs_match, include_certs)
        else:
            br.restore(vs_match)

    else:
        parser.print_help()
