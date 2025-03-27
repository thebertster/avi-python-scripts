#!/usr/bin/env python

"""Script to enumerate the mapping between configured VrfContexts and the
network namespaces used on a specific Service Engine."""

import argparse
import getpass
from fnmatch import fnmatch

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
                        help='FQDN or IP address of Avi Controller')
    parser.add_argument('-u', '--user', help='Avi API Username',
                        default='admin')
    parser.add_argument('-p', '--password', help='Avi API Password')
    parser.add_argument('-t', '--tenant', help='Tenant',
                        default='admin')
    parser.add_argument('-x', '--apiversion', help='Avi API version')

    parser.add_argument('-s', '--se', help='SE names to match',
                        default='*')

    args = parser.parse_args()

    if args:
        # If not specified on the command-line, prompt the user for the
        # controller IP address and/or password

        controller = args.controller
        user = args.user
        password = args.password
        tenant = args.tenant
        api_version = args.apiversion
        se_match = args.se

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

        service_engines = api.get_objects_iter('serviceengine',
                                               params={'join_subresources':
                                                       'vnicdb'})

        for service_engine in service_engines:
            se_name = service_engine['name']
            if fnmatch(se_name, se_match):
                print(f'Service Engine {se_name}:')
                table = []
                for vrf in service_engine['vnicdb'][0]['vrf']:
                    vrf_name = vrf['vrf_context']['name']
                    namespace = vrf['ns']
                    if vrf_name != 'seagent-default':
                        table.append([vrf_name, namespace])
                print(tabulate(table, headers=['VRF', 'Namespace'],
                               tablefmt='grid'))
                print()
    else:
        parser.print_help()
