#!/usr/bin/env python

import argparse
import getpass

import requests
import urllib3
from avi.sdk.avi_api import ApiSession
from tempfile import TemporaryDirectory
from subprocess import run

# Disable certificate warnings

if hasattr(requests.packages.urllib3, 'disable_warnings'):
    requests.packages.urllib3.disable_warnings()

if hasattr(urllib3, 'disable_warnings'):
    urllib3.disable_warnings()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-c', '--controller',
                        help='FQDN or IP address of Avi Controller')
    parser.add_argument('-u', '--user', help='Avi API Username',
                        default='admin')
    parser.add_argument('-p', '--password', help='Avi API Password')
    parser.add_argument('-t', '--tenant', help='Tenant',
                        default='admin')
    parser.add_argument('-x', '--apiversion', help='Avi API version')
    parser.add_argument('-tx', '--tfversion', help='Terraform provider version')
    parser.add_argument('objecttype', help='Type of the object')
    parser_n = parser.add_mutually_exclusive_group()
    parser_n.add_argument('-s', '--search',
                          help='Search for object names containing string')
    parser_n.add_argument('-n', '--names',
                          help='Comma-separated list of object names')
    parser.add_argument('filename', help='Output .tf file for resources')

    args = parser.parse_args()

    if args:
        # If not specified on the command-line, prompt the user for the
        # controller IP address and/or password

        controller = args.controller
        user = args.user
        password = args.password
        tenant = args.tenant
        api_version = args.apiversion
        tf_version = args.tfversion
        object_type = args.objecttype
        object_names = args.names
        object_search = args.search
        output_fn = args.filename

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

        params = {'fields': 'uuid,name'}

        if object_search:
            params['search'] = f'(name,{object_search})'
        elif object_names:
            if ',' in object_names:
                params['name.in'] = object_names
            else:
                params['name'] = object_names

        matching_objects = api.get_objects_iter(object_type, tenant=tenant,
                                                params=params)

        print('Preparing environment', end='')

        with TemporaryDirectory() as td:
            with open(f'{td}/main.tf', mode='w', encoding='UTF-8') as tf_main:
                tf_version = tf_version or api_version
                tf_boilerplate = ['terraform {\n',
                                  '  required_providers {\n',
                                  '    avi = {\n',
                                  '      source = "vmware/avi"\n',
                                  f'      version = "{tf_version}"\n',
                                  '    }\n',
                                  '  }\n',
                                  '}\n',
                                  '\n',
                                  'provider "avi" {\n',
                                  f'  avi_username    = "{user}"\n',
                                  f'  avi_tenant      = "{tenant}"\n',
                                  f'  avi_password    = "{password}"\n',
                                  f'  avi_controller  = "{controller}"\n',
                                  f'  avi_version     = "{api_version}"\n'
                                  '}\n',
                                  '\n']
                tf_main.writelines(tf_boilerplate)
                resources = []
                for obj in matching_objects:
                    print('.', end='')
                    object_uuid = obj['uuid']
                    object_names = obj.get('name', object_uuid)
                    rs = f'resource "avi_{object_type}" "{object_uuid}" {{ }}\n'
                    tf_main.write(rs)
                    resources.append((object_uuid, object_names))
                tf_main.flush()
                print()

            print(f'Initializing Terraform (vmware/avi {tf_version})...')

            p = run(['terraform', f'-chdir={td}', 'init'],
                    capture_output=True, check=False)

            if p.returncode:
                print('Error invoking terraform init:')
                print(p.stderr.decode('UTF-8'))
            else:
                print('Importing resources...')
                with open(output_fn, mode='wb') as output:
                    for object_uuid, object_names in resources:
                        print(f'Importing {object_uuid} ({object_names})')
                        p = run(['terraform',
                                 f'-chdir={td}',
                                 'import',
                                 f'avi_{object_type}.{object_uuid}',
                                 f'{object_uuid}'],
                                capture_output=True,
                                check=False)
                        if p.returncode:
                            print('Error invoking terraform import:')
                            print(p.stderr.decode('UTF-8'))
                            continue
                        p = run(['terraform',
                                f'-chdir={td}',
                                 'state',
                                 'show',
                                 '-no-color',
                                 f'avi_{object_type}.{object_uuid} '],
                                capture_output=True,
                                check=False)
                        if p.returncode:
                            print('Error invoking terraform state show:')
                            print(p.stderr.decode('UTF-8'))
                            continue
                        output.write(bytes(f'# {object_names}\n',
                                           encoding='UTF-8'))
                        output.write(p.stdout)
                        output.write(b'\n\n')
                print()
                print(f'Resources have been written to {output_fn}')

    else:
        parser.print_help()
