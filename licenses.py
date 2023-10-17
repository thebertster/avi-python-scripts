#!/usr/bin/env python

import argparse
import getpass
from datetime import datetime

import requests
import urllib3
from avi.sdk.avi_api import ApiSession
from tabulate import tabulate


def try_parsing_date(possible_date):
    """
    Try to parse a date using several formats, warn about
    problematic value if the possible_date does not match
    any of the formats tried
    """
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(possible_date, fmt)
        except ValueError:
            pass
    raise ValueError(f"Non-valid date format for field: '{possible_date}'")

if hasattr(requests.packages.urllib3, 'disable_warnings'):
    requests.packages.urllib3.disable_warnings()

if hasattr(urllib3, 'disable_warnings'):
    urllib3.disable_warnings()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-c', '--controller',
                        help='FQDN or IP address of Avi Vantage controller')
    parser.add_argument('-u', '--user', help='Avi Vantage username',
                        default='admin')
    parser.add_argument('-p', '--password', help='Avi Vantage password')
    parser.add_argument('-x', '--apiversion', help='NSX ALB API version')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-l', '--list', action='store_true',
                       help='List licenses', default=False)
    group.add_argument('-d', '--delete', help='Delete specified license by ID')
    group.add_argument('-dx', '--deleteexpired', action='store_true',
                       help='Delete all expired licenses',
                       default=False)
    args = parser.parse_args()

    if args:
        # If not specified on the command-line, prompt the user for the
        # controller IP address and/or password

        controller = args.controller
        user = args.user
        password = args.password
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

        if args.list:
            licenses = api.get('licensing').json()
            print('Licenses present:')
            license_list=[]
            for lic in licenses['licenses']:
                license_id = lic.get('license_id', '???')
                license_name = lic.get('license_name', '???')
                license_valid_until = lic.get('valid_until', None)
                license_expiry = (try_parsing_date(license_valid_until)
                                  if license_valid_until else '???')
                license_cores = lic.get('cores', 'N/A')
                license_list.append([license_expiry, license_cores,
                                     license_id, license_name])
            print(tabulate(license_list,
                           headers=['Expires', 'SUs', 'License ID', 'Name'],
                           tablefmt='outline'))
        elif args.deleteexpired:
            licenses = api.get('licensing').json()
            now = datetime.now()
            for lic in licenses['licenses']:
                license_id = lic.get('license_id', '???')
                license_name = lic.get('license_name', '???')
                license_valid_until = lic.get('valid_until', None)
                if license_valid_until:
                    license_expiry = try_parsing_date(lic['valid_until'])
                    if license_expiry < now:
                        print(f'Deleting license {license_id} : {license_name}')
                        try:
                            r = api.delete(f'licensing/{license_id}')
                        except:
                            print('Could not delete license')
        elif args.delete:
            print(f'Deleting license {args.delete}')
            try:
                r = api.delete(f'licensing/{args.delete}')
            except:
                print('Could not delete license')
    else:
        parser.print_help()