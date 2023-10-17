#!/usr/bin/env python

import argparse
import getpass

import requests
import urllib3
from avi.sdk.avi_api import ApiSession
from tabulate import tabulate

# Disable certificate warnings

if hasattr(requests.packages.urllib3, 'disable_warnings'):
    requests.packages.urllib3.disable_warnings()

if hasattr(urllib3, 'disable_warnings'):
    urllib3.disable_warnings()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-c', '--controller',
                        help='FQDN or IP address of NSX ALB Controller')
    parser.add_argument('-u', '--user', help='NSX ALB API Username',
                        default='admin')
    parser.add_argument('-p', '--password', help='NSX ALB API Password')
    parser.add_argument('-x', '--apiversion', help='NSX ALB API version')
    op_parser = parser.add_subparsers(help='Operation to perform',
                                      dest='operation')
    list_parser = op_parser.add_parser('list', help='List tokens')
    list_parser.add_argument('-u', '--username',
                             help='List tokens for specified user')
    create_parser = op_parser.add_parser('create',
                                         help='Create token for a user')
    create_parser.add_argument('username', help='User name')
    create_parser.add_argument('-e', '--expires',
                               help='Destroy token after specified '
                                    'number of hours (0-87600)', default=0,
                                    choices=range(0, 87600),
                                    type=int)
    delete_parser = op_parser.add_parser('delete', help='Delete token')
    delete_parser.add_argument('uuid', help='UUID of token to delete')

    args = parser.parse_args()

    if args:
        # If not specified on the command-line, prompt the user for the
        # controller IP address and/or password

        controller = args.controller
        user = args.user
        password = args.password
        tenant = 'admin'
        api_version = args.apiversion
        operation = args.operation

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

        if operation == 'list':
            auth_user = args.username

            tokens = api.get_objects_iter('authtoken',
                                          params={'include_name': True})

            token_list = []

            for token in tokens:
                token_user = token['user_ref'].split('#')[1]
                if (not auth_user or token_user == auth_user):
                    token_list.append([token['uuid'],
                                       token_user,
                                       token.get('expires_at', 'Single Use'),
                                       token['token']])
            print(tabulate(token_list,
                           headers=['UUID', 'User', 'Expires', 'Token'],
                           tablefmt='outline'))
        elif operation == 'delete':
            uuid = args.uuid

            rsp = api.delete(f'authtoken/{uuid}')
            if rsp.status_code == 404:
                print(f'Could not find token with UUID {uuid}')
            elif rsp.status_code == 204:
                print(f'Deleted token {uuid}')
            else:
                raise Exception(f'Error deleting token {uuid}: {rsp.text}')
        elif operation == 'create':
            auth_user = args.username
            expires = args.expires

            obj_data = {'username': auth_user,
                         'hours': expires}

            rsp = api.post('authtoken', data=obj_data)
            if rsp.status_code == 200:
                token_info = rsp.json()
                print(tabulate([[token_info['uuid'],
                                token_info.get('expires_at', 'Single Use'),
                                token_info['token']]],
                               headers=['UUID', 'Expires', 'Token'],
                               tablefmt='outline'))
            else:
                raise Exception(f'Error creating token for '
                                f'{auth_user}: {rsp.text}')
    else:
        parser.print_help()
