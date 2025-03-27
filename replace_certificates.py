#!/usr/bin/env python

"""Script to search and replace SSL certificate bindings across multiple
Virtual Services."""

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
    parser.add_argument('search_certs',
                        help='Comma-separated list of certificates '
                        'to search for')
    parser.add_argument('replace_certs',
                        help='Comma-separated list of replacement '
                        'certificates')

    args = parser.parse_args()

    if args:
        # If not specified on the command-line, prompt the user for the
        # controller IP address and/or password

        controller = args.controller
        user = args.user
        password = args.password
        tenant = args.tenant
        api_version = args.apiversion
        search_certs = args.search_certs.split(',')
        replace_certs = args.replace_certs.split(',')

        if len(search_certs) != len(replace_certs):
            raise ValueError('Number of certificates to search for '
                             'must match the number of replacements!')

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

        for search, replace in zip(search_certs, replace_certs):
            if search.startswith('sslkeyandcertificate-'):
                rsp = api.get(f'sslkeyandcertificate/{search}',
                              tenant=tenant,
                              params={'fields': 'uuid,url,name'})
                if rsp.status_code < 300:
                    s_cert = rsp.json()
                else:
                    s_cert = None
            else:
                s_cert = api.get_object_by_name('sslkeyandcertificate',
                                                search,
                                                tenant=tenant,
                                                params={'fields':
                                                        'uuid,url,name'})

            if replace.startswith('sslkeyandcertificate-'):
                rsp = api.get(f'sslkeyandcertificate/{replace}',
                              tenant=tenant,
                              params={'fields': 'uuid,url,name'})
                if rsp.status_code < 300:
                    r_cert = rsp.json()
                else:
                    r_cert = None
            else:
                r_cert = api.get_object_by_name('sslkeyandcertificate',
                                                replace,
                                                tenant=tenant,
                                                params={'fields':
                                                        'uuid,url,name'})

            if s_cert and r_cert:
                s_uuid = s_cert['uuid']
                s_url = s_cert['url']
                r_url = r_cert['url']
                s_name = s_cert['name']
                r_name = r_cert['name']
                vs_params = {'refers_to': f'sslkeyandcertificate:{s_uuid}',
                             'fields': 'ssl_key_and_certificate_refs'}
                vs_list = api.get_objects_iter('virtualservice',
                                               params=vs_params,
                                               tenant=tenant)
                for vs in vs_list:
                    vs_name = vs['name']
                    print(f'Updating VS {vs_name}: {s_name} -> {r_name}')
                    cert_refs = vs.get('ssl_key_and_certificate_refs', [])
                    new_cert_refs = [r_url if c == s_url else c
                                     for c in cert_refs]
                    data = {
                        'json_patch': [
                            {
                                'op': 'replace',
                                'path': '/ssl_key_and_certificate_refs',
                                'value': new_cert_refs
                            }
                        ]
                    }

                    upd = api.patch(f'virtualservice/{vs["uuid"]}',
                                    json.dumps(data))
                    if upd.status_code < 300:
                        print(f'Updated Virtual Service {vs_name}')
                    else:
                        print(f'Failed to update Virtual Service {vs_name}')
                        print(f'Error: {upd.status_code}: {upd.text}')
            else:
                if not s_cert:
                    print(f'Unable to find certificate {search}')
                if not r_cert:
                    print(f'Unable to find certificate {replace}')
    else:
        parser.print_help()
