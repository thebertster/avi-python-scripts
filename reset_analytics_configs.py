#!/usr/bin/env python

import argparse
import getpass
import json

import requests
import urllib3
from avi.sdk.avi_api import ApiSession

# Disable certificate warnings

if hasattr(requests.packages.urllib3, 'disable_warnings'):
    requests.packages.urllib3.disable_warnings()

if hasattr(urllib3, 'disable_warnings'):
    urllib3.disable_warnings()

CRITERIA = {
    'clientinsights': {
        'filter': {'search': '(client_insights,IVE)'},
        'patch_data': {
            'json_patch': [
                {
                    'op': 'replace',
                    'path': '/analytics_policy/client_insights',
                            'value': 'NO_INSIGHTS'
                }
            ]
        }
    },
    'nonsiglogs': {
        'filter': {'analytics_policy.full_client_logs.enabled': True},
        'patch_data': {
            'json_patch': [
                {
                    'op': 'replace',
                    'path': '/analytics_policy/full_client_logs/enabled',
                            'value': False
                }
            ]
        }
    },
    'realtimemetrics': {
        'filter': {'analytics_policy.metrics_realtime_update.enabled': True},
        'patch_data': {
            'json_patch': [
                {
                    'op': 'replace',
                    'path': '/analytics_policy/metrics_realtime_update/enabled',
                            'value': False
                }
            ]
        }
    }
}


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
    parser.add_argument('-a', '--actions',
                        help='Actions to take',
                        choices=CRITERIA.keys(),
                        action='extend',
                        nargs='*',
                        type=str)
    parser.add_argument('-e', '--exclude',
                        help='Exclude specific virtual services',
                        action='extend',
                        nargs='*',
                        type=str)
    parser.add_argument('-l', '--list',
                        help='List matching VirtualServices but take no action',
                        action='store_true')

    args = parser.parse_args()

    if args:
        # If not specified on the command-line, prompt the user for the
        # controller IP address and/or password

        controller = args.controller
        user = args.user
        password = args.password
        tenant = args.tenant
        api_version = args.apiversion
        actions = args.actions or CRITERIA.keys()
        exclude = args.exclude
        list_only = args.list

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

        for action in actions:
            print()
            print(f'Checking {action}...')

            params = CRITERIA[action]['filter']
            params['fields'] = 'uuid,tenant_ref'
            params['include_name'] = True

            patch_data = CRITERIA[action]['patch_data']

            resp = api.get('virtualservice',
                           params=params,
                           tenant=tenant)
            if resp.status_code < 300:
                resp_json = resp.json()
                count = resp_json['count']
                if count == 0:
                    print('No Virtual Services found')
                vs_list = resp_json['results']
                print(f'{count} Virtual Service(s) found')

                for vs in vs_list:
                    vs_name = vs['name']
                    vs_uuid = vs['uuid']
                    tenant_name = vs['tenant_ref'].split('#')[1]
                    print(f'Found VS: {vs_name}'
                          f'{"@"+tenant_name if tenant == "*" else ""}')
                    if list_only:
                        continue
                    if exclude and vs_name in exclude:
                        print('VS is in exclusion list: Skipping')
                        continue
                    upd = api.patch(f'virtualservice/{vs_uuid}',
                                    data=json.dumps(patch_data),
                                    tenant=tenant_name)
                    if upd.status_code < 300:
                        print(f'Updated Virtual Service {vs_name}')
                    else:
                        print(f'Failed to update Virtual Service {vs_name}')
                        print(f'Error: {upd.status_code}: {upd.text}')
            else:
                print(f'VS Query returned error: {resp.text}')
    else:
        parser.print_help()
