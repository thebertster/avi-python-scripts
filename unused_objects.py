#!/usr/bin/env python

"""Script to report on and/or remove 'orphaned' configuration objects that
are no longer referenced."""

import argparse
import getpass

import requests
import urllib3
from avi.sdk.avi_api import ApiSession

OBJECT_TYPES = {'sslkeyandcertificate', 'hardwaresecuritymodulegroup',
                'dnspolicy', 'stringgroup', 'wafpolicy', 'geodb',
                'alertscriptconfig', 'pool', 'networkservice', 'application',
                'ipaddrgroup', 'errorpagebody', 'availabilityzone',
                'errorpageprofile', 'analyticsprofile', 'sslprofile',
                'botconfigconsolidator', 'gslbgeodbprofile', 'tenant',
                'networksecuritypolicy', 'ssopolicy', 'jwtserverprofile',
                'healthmonitor', 'vsvip', 'cloudconnectoruser', 'botmapping',
                'pingaccessagent', 'autoscalelaunchconfig', 'actiongroupconfig',
                'applicationprofile', 'alertsyslogconfig', 'pkiprofile',
                'vsdatascriptset', 'trafficcloneprofile',
                'customipamdnsprofile', 'securitypolicy', 'ipreputationdb',
                'protocolparser', 'serviceenginegroup', 'httppolicyset',
                'snmptrapprofile', 'applicationpersistenceprofile', 'poolgroup',
                'serviceengine', 'networkprofile', 'wafcrs',
                'botdetectionpolicy', 'vcenterserver', 'scheduler', 'network',
                'webhook', 'alertconfig', 'authmappingprofile',
                'serverautoscalepolicy', 'icapprofile',
                'ipamdnsproviderprofile', 'alert', 'labelgroup', 'wafprofile',
                'vrfcontext', 'l4policyset', 'prioritylabels',
                'wafpolicypsmgroup', 'natpolicy', 'cloud',
                'botipreputationtypemapping', 'role', 'authprofile',
                'alertemailconfig', 'certificatemanagementprofile',
                'virtualservice', 'gslbservice'}

EXCLUDE_OBJECT_TYPES = {'virtualservice', 'gslbservice', 'network', 'wafcrs'}

SPECIAL_OBJECT_NAMES = {'vrfcontext': ['management'],
                        'certificatemanagementprofile':
                            ['LetsEncryptCertificateManagementProfile'],
                        'ipaddrgroup': ['Internal'],
                        'autoscalelaunchconfig':
                            ['default-autoscalelaunchconfig'],
                        'protocolparser': ['Default-DHCP', 'Default-Radius',
                                           'Default-FIX', 'Default-TLS'],
                        'role': ['Application-Admin', 'Tenant-Admin',
                                 'Application-Operator', 'Security-Admin',
                                 'WAF-Admin'],
                        'actiongroupconfig': ['Syslog-Audit-Persistence'],
                        'serviceenginegroup': ['Default-Group'],
                        'vsdatascriptset': ['Default-PASV-FTP',
                                            'Default-ACTIVE-FTP',
                                            'Default-FULL-FTP'],
                        'alertconfig': ['Syslog-System-Events'],
                        'errorpageprofile': ['Custom-Error-Page-Profile']}

DELETE_NEVER = 0
DELETE_PROMPT = 1
DELETE_TYPE = 2
DELETE_ALL = 3

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
    parser.add_argument('-o', '--objecttypes',
                        help=f'Comma-separated list of types of object to check'
                             f' from {OBJECT_TYPES}')
    parser.add_argument('-i', '--includesystem',
                        help='Include default System-XXX objects',
                        action='store_true')
    parser.add_argument('-v', '--verbose',
                        help='Include UUID in output',
                        action='store_true')
    parser_d = parser.add_mutually_exclusive_group()
    parser_d.add_argument('-d', '--delete',
                          help='Allow deletion of unused objects '
                          '(with confirmation)',
                          action='store_true')
    parser_d.add_argument('-f', '--force',
                          help='Delete unused objects without prompting',
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
        all_objects = not args.objecttypes
        object_types = (list(OBJECT_TYPES - EXCLUDE_OBJECT_TYPES) if all_objects
                        else
                        set(args.objecttypes.lower().split(',')) & OBJECT_TYPES)
        include_system = args.includesystem
        verbose = args.verbose
        deletion = DELETE_ALL if args.force else (DELETE_PROMPT if args.delete
                                                  else DELETE_NEVER)

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

        if deletion == DELETE_PROMPT:
            print('Deletion action choices:')
            print('[Y]es = Delete the current object')
            print('[N]o = Do not delete the current object')
            print('[S]kip = Do not delete any more objects of this type')
            print('[T]ype = Delete all unused objects of this type')
            print('[A]ll = Delete all unused objects of all types')
            print()

        for object_type in object_types:
            unused_objects = api.get_objects_iter(object_type, tenant=tenant,
                                                  params={
                                                      'referred_by': 'any:none',
                                                      'fields': 'tenant_ref',
                                                      'include_name': True})
            filtered_unused = [(u_obj['name'],
                                u_obj.get('tenant_ref', '').split('#')[1],
                                u_obj['uuid'],
                                u_obj['url'])
                               for u_obj in unused_objects
                               if (include_system or not
                                   (u_obj['name'].startswith('System-')
                                    or u_obj['name'] in
                                    SPECIAL_OBJECT_NAMES.get(object_type, [])))]
            if filtered_unused or not all_objects:
                print()
                print(f'Unused {object_type} objects:',
                      end=' NONE\n' if not filtered_unused else '\n')

            for u_obj in filtered_unused:
                u_obj_info = ' / '.join(u_obj[:(3 if verbose else 2
                                                if tenant == '*' else 1)])
                print(u_obj_info)
                delete_this = deletion in (DELETE_TYPE, DELETE_ALL)
                if deletion == DELETE_PROMPT:
                    del_ch = input('Delete [Y]es, [N]o, '
                                   '[S]kip, [T]ype, [A]ll?').lower()
                    if 'yes'.startswith(del_ch):
                        delete_this = True
                    elif 'type'.startswith(del_ch):
                        delete_this = True
                        deletion = DELETE_TYPE
                    elif 'all'.startswith(del_ch):
                        delete_this = True
                        deletion = DELETE_ALL
                    elif 'skip'.startswith(del_ch):
                        break
                if delete_this:
                    print(f'Deleting {" / ".join(u_obj[:3])}...', end='')
                    result = api.delete(u_obj[3].split('/api/')[1],
                                        tenant=u_obj[1])
                    if result.status_code == 204:
                        print('OK')
                    else:
                        print('Failed with {result.status_code}')
                    print()

            if deletion == DELETE_TYPE:
                deletion = DELETE_PROMPT
    else:
        parser.print_help()
