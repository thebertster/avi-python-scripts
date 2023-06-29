#!/usr/bin/env python

import argparse
import getpass
import urllib3
import requests
from avi.sdk.avi_api import ApiSession

# Common utility functions

def get_all(api, *args, params=None, **kwargs):
    # Iterates through paged results, returning all

    retries = 0
    page = 1
    results = []
    if not params:
        params = {}
    if 'page_size' not in params:
        params['page_size'] = 50
    while page:
        params['page'] = page
        r = api.get(*args, params=params, **kwargs)
        if r.status_code in (401, 419) and retries < 5:
            ApiSession.reset_session(api)
            retries += 1
            continue
        elif r.status_code != 200:
            raise(RuntimeError(f'Unexpected error in get_paged: {r}'))
        r_json = r.json()
        results.extend(r_json['results'])
        if 'next' in r_json:
            page += 1
        else:
            page = 0
    return {'count': len(results),
            'results': results}

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
    else:
        parser.print_help()
