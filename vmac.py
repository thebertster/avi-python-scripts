#!/usr/bin/env python

import argparse
import getpass

import requests
import urllib3
from avi.sdk.avi_api import ApiSession
from tabulate import tabulate
from hashlib import md5

# Disable certificate warnings

if hasattr(requests.packages.urllib3, 'disable_warnings'):
    requests.packages.urllib3.disable_warnings()

if hasattr(urllib3, 'disable_warnings'):
    urllib3.disable_warnings()


def get_vmac(seg_uuid, floating_ip):
    segrp_fip_str = seg_uuid + floating_ip

    vmac_id = md5(segrp_fip_str.encode('utf-8')).hexdigest()

    vmac = '0e:' + ':'.join(['%0.2x' % (int(vmac_id[i:i+2], base=16) ^ 255)
                            for i in range(0, 10, 2)])

    return vmac


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
    parser.add_argument('-n', '--networkservice', help='Network Service')

    args = parser.parse_args()

    if args:
        # If not specified on the command-line, prompt the user for the
        # controller IP address and/or password

        controller = args.controller
        user = args.user
        password = args.password
        tenant = args.tenant
        api_version = args.apiversion
        network_service = args.networkservice

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

        if network_service:
            obj = api.get_object_by_name('networkservice', network_service,
                                         params={'include_name': True},
                                         tenant=tenant)
            network_services = [obj] if obj else []
        else:
            network_services = list(
                api.get_objects_iter('networkservice',
                                     params={'include_name': True},
                                     tenant=tenant))

        if network_services:
            ns_table = []
            for ns in network_services:
                ns_name = ns['name']
                se_group_ref = ns['se_group_ref'].split(
                    '/api/serviceenginegroup/')[1].split('#')
                se_group_uuid = se_group_ref[0]
                se_group_name = se_group_ref[1]
                vrf_name = ns['vrf_ref'].split('#')[1]
                cloud_name = ns['cloud_ref'].split('#')[1]
                rs = ns.get('routing_service', {})
                vmac_enabled = rs['enable_vmac']
                floating_intf_ips = rs.get('floating_intf_ip', [])
                floating_intf_ips.extend(rs.get('floating_intf_ip_se_2', []))
                for fip in floating_intf_ips:
                    fip_addr = fip['addr']
                    vmac = get_vmac(se_group_uuid, fip_addr)
                    ns_table.append([ns_name, cloud_name, vrf_name,
                                     se_group_name, fip_addr, vmac,
                                     vmac_enabled])
            print(tabulate(ns_table, headers=['Network Service', 'Cloud',
                                              'VRF', 'SE Group',
                                              'Floating IP', 'VMAC',
                                              'VMAC Enabled'],
                           tablefmt='outline'))
        else:
            print('No network services found.')
    else:
        parser.print_help()
