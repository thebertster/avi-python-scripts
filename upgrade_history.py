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
    parser.add_argument('-t', '--tenant', help='Tenant',
                        default='admin')
    parser.add_argument('-x', '--apiversion', help='NSX ALB API version')

    args = parser.parse_args()

    if args:
        # If not specified on the command-line, prompt the user for the
        # controller IP address and/or password

        controller = args.controller
        user = args.user
        password = args.password
        tenant = args.tenant
        api_version = args.apiversion

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

        rsp = api.get('upgradestatusinfo',
                      params={'include_history': True,
                              'node_type': 'NODE_CONTROLLER_CLUSTER'},
                      tenant=tenant)
        if rsp.status_code < 300:
            upgrade_status = rsp.json().get('results', [{}])[0]
            upgrade_history = upgrade_status.get('history', [])
            history = []
            for upgrade_info in upgrade_history:
                history.append([
                    upgrade_info.get('end_time', ''),
                    upgrade_info.get('version', ''),
                    upgrade_info.get('patch_version', ''),
                    upgrade_info.get('state', {'state': ''})['state']
                ])
            if 'end_time' in upgrade_status:
                history.append([
                    upgrade_status.get('end_time', ''),
                    upgrade_status.get('version', ''),
                    upgrade_status.get('patch_version', ''),
                    upgrade_status.get('state', {'state': ''})['state']
                ])
            print(tabulate(history,
                headers=['Completed', 'Version', 'Patch', 'State'],
                tablefmt='outline'))
        else:
            print('Could not retrieve upgrade history.')
    else:
        parser.print_help()
