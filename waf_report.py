#!/usr/bin/env python

"""Script to generate a summary report of WAF Configurations used by
Virtual Services."""

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
                        help='FQDN or IP address of Avi Controller')
    parser.add_argument('-u', '--user', help='Avi API Username',
                        default='admin')
    parser.add_argument('-p', '--password', help='Avi API Password')
    parser.add_argument('-t', '--tenant', help='Tenant',
                        default='admin')
    parser.add_argument('-x', '--apiversion', help='Avi API version')

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

        waf_params = {'fields': 'name,uuid,mode,paranoia_level'}
        waf_policies = api.get_objects_iter('wafpolicy', tenant=tenant,
                                            params=waf_params)

        waf_policy_list = []

        for waf_policy in waf_policies:
            waf_policy_name = waf_policy['name']
            waf_policy_uuid = waf_policy['uuid']
            waf_policy_mode = waf_policy['mode']
            waf_policy_paranoia_level = waf_policy['paranoia_level']
            vss = api.get_objects_iter('virtualservice', tenant=tenant,
                                       params={
                                           'refers_to':
                                           f'wafpolicy:{waf_policy_uuid}',
                                           'fields': 'name'})
            vs_names = ','.join([vs['name'] for vs in vss])

            waf_policy_list.append([waf_policy_name, vs_names,
                                    waf_policy_mode, waf_policy_paranoia_level])

        print(tabulate(waf_policy_list, headers=['WAF Policy',
                                                 'Virtual Services',
                                                 'Policy Mode',
                                                 'Paranoia Level'],
                       tablefmt='outline'))

    else:
        parser.print_help()
