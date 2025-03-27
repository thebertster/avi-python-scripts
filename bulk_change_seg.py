#!/usr/bin/env python

"""Script to automate changing Service Engine Group for Virtual Services
in bulk."""

import argparse
import getpass

import requests
import urllib3
from avi.sdk.avi_api import ApiSession

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
    parser.add_argument('source_seg',
                        help='Source SE Group')
    parser.add_argument('dest_seg',
                        help='Destination SE Group')
    parser.add_argument('-i', '--include',
                        help='Comma-separated list of VSs to include. '
                             'If unspecified, all VSs will be included.')
    parser.add_argument('-e', '--exclude',
                        help='Comma-separated list of VSs to exclude.')

    args = parser.parse_args()

    if args:
        # If not specified on the command-line, prompt the user for the
        # controller IP address and/or password

        controller = args.controller
        user = args.user
        password = args.password
        tenant = args.tenant
        api_version = args.apiversion
        source_seg = args.source_seg
        dest_seg = args.dest_seg
        vs_include = args.include.split(',') if args.include else None
        vs_exclude = args.exclude.split(',') if args.exclude else None

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

        source_seg_obj = api.get_object_by_name('serviceenginegroup',
                                                source_seg,
                                                tenant=tenant,
                                                params={'fields':
                                                        'uuid,url,name'})

        if not source_seg_obj:
            print(f'Unable to locate SE Group {source_seg}')
            exit()

        source_seg_uuid = source_seg_obj['uuid']

        dest_seg_obj = api.get_object_by_name('serviceenginegroup',
                                              dest_seg,
                                              tenant=tenant,
                                              params={'fields':
                                                      'uuid,url,name'})

        if not dest_seg_obj:
            print(f'Unable to locate SE Group {dest_seg}')
            exit()

        dest_seg_uuid = dest_seg_obj['uuid']

        patch_data = {
            'json_patch': [
                {
                    'op': 'replace',
                    'path': '/se_group_ref',
                            'value': dest_seg_obj['url']
                }
            ]
        }

        vs_list = api.get_objects_iter('virtualservice', tenant=tenant,
                params={'refers_to':f'serviceenginegroup:{source_seg_uuid}'})

        successes = 0
        failures = 0
        skips = 0

        fail_list = []

        for vs in vs_list:
            vs_name = vs['name']
            vs_uuid = vs['uuid']

            if vs_include and vs_name not in vs_include:
                print(f'Skipping VS {vs_name} as it is not in INCLUDE list')
                skips += 1
                continue

            if vs_exclude and vs_name in vs_exclude:
                print(f'Skipping VS {vs_name} as it is in EXCLUDE list')
                skips += 1
                continue

            upd = api.patch(f'virtualservice/{vs_uuid}', tenant=tenant,
                            data=patch_data)

            if upd.status_code < 300:
                print(f'Updated Virtual Service {vs_name}')
                successes += 1
            else:
                print(f'Failed to update Virtual Service {vs_name}')
                print(f'Error: {upd.status_code}: {upd.text}')
                fail_list.append(f'"{vs_name}"')
                failures += 1

        print('Finished.')
        print(f'{successes} Virtual Service{"" if successes == 1 else "s"} '
              f'successfully updated.')
        print(f'{skips} Virtual Service{"" if skips == 1 else "s"} skipped.')
        print(f'{failures} Virtual Service{"" if failures == 1 else "s"} '
              f'failed to update{":" if failures else "."}')

        if fail_list:
            print(','.join(fail_list))

    else:
        parser.print_help()
