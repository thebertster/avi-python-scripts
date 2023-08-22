#!/usr/bin/env python

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

UNSAFE_CIPHERS = {
    # Below is not in Controller's unsafe list but probably should be!
    #'TLS_RSA_WITH_3DES_EDE_CBC_SHA',
    'TLS_ECDHE_ECDSA_WITH_AES_128_CBC_SHA',
    'TLS_ECDHE_ECDSA_WITH_AES_128_CBC_SHA256',
    'TLS_ECDHE_ECDSA_WITH_AES_256_CBC_SHA',
    'TLS_ECDHE_ECDSA_WITH_AES_256_CBC_SHA384',
    'TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA',
    'TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA256',
    'TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA',
    'TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA384',
    'TLS_RSA_WITH_AES_128_GCM_SHA256',
    'TLS_RSA_WITH_AES_256_GCM_SHA384',
    'TLS_RSA_WITH_AES_256_CBC_SHA256',
    'TLS_RSA_WITH_AES_128_CBC_SHA',
    'TLS_RSA_WITH_AES_128_CBC_SHA256',
    'TLS_RSA_WITH_AES_256_CBC_SHA'
}

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
    parser.add_argument('-n', '--name', help='SSL Profile search filter',
                        default='')
    parser.add_argument('-e', '--exclude', help='Comma-separated list of '
                        'SSL Prorilfes to exlude',
                        default='')

    args = parser.parse_args()

    if args:
        # If not specified on the command-line, prompt the user for the
        # controller IP address and/or password

        controller = args.controller
        user = args.user
        password = args.password
        tenant = args.tenant
        api_version = args.apiversion
        name = args.name
        exclusions = args.exclude.lower().split(',')

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

        ssl_profiles = api.get_objects_iter('sslprofile', tenant=tenant,
                                            params={'isearch':
                                                f'(name,{name})'})
        for ssl_profile in ssl_profiles:
            profile_name = ssl_profile['name']
            print(f'Processing SSL Profile {profile_name}...', end='')
            if profile_name.lower() in exclusions:
                print('Skipping')
                continue
            ciphers = set(ssl_profile.get('cipher_enums', []))
            ciphers_removed = ciphers & UNSAFE_CIPHERS
            if ciphers_removed:
                print('')
                print('Removing the following ciphers:')
                print(', '.join(ciphers_removed), end='...')
                ssl_profile['cipher_enums'] = list(ciphers - UNSAFE_CIPHERS)
                resp = api.put(f'sslprofile/{ssl_profile["uuid"]}', ssl_profile,
                            tenant=tenant)
                if resp.status_code == 200:
                    print('OK!')
                else:
                    print('Got error %d' % (resp.status_code))
                print()
            else:
                print('No unsafe ciphers')
    else:
        parser.print_help()
