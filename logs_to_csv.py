#!/usr/bin/env python

import argparse
import csv
import getpass
from datetime import datetime, timezone
from os import devnull

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
                        help='FQDN or IP address of NSX ALB Controller')
    parser.add_argument('-u', '--user', help='NSX ALB API Username',
                        default='admin')
    parser.add_argument('-p', '--password', help='NSX ALB API Password')
    parser.add_argument('-t', '--tenant', help='Tenant',
                        default='admin')
    parser.add_argument('-x', '--apiversion', help='NSX ALB API version')
    parser.add_argument('-f', '--filename', help='Output to named CSV file')
    parser.add_argument('-in', '--includenonsignificantlogs',
                        help='Include non-significant logs',
                        action='store_true')
    parser.add_argument('-iu', '--includeuserdefinedlogs',
                        help='Include user-defined logs',
                        action='store_true')
    parser.add_argument('-es', '--excludesignificantlogs',
                        help='Exclude significant logs',
                        action='store_true')
    parser.add_argument('virtualservice',
                        help='Name of the Virtual Service')
    parser.add_argument('startdatetime',
                        help='Start date and time for exported logs '
                             'in ISO8601 format, e.g. 2024-01-01T00:00.')
    parser.add_argument('enddatetime',
                        help='Start date and time for exported logs '
                             'in ISO8601 format, e.g. 2024-01-01T00:00.')

    args = parser.parse_args()

    if args:
        # If not specified on the command-line, prompt the user for the
        # controller IP address and/or password

        controller = args.controller
        user = args.user
        password = args.password
        tenant = args.tenant
        api_version = args.apiversion
        vs_name = args.virtualservice
        filename = args.filename or devnull

        params = {'nf': bool(args.includenonsignificantlogs),
                  'adf': not bool(args.excludesignificantlogs),
                  'udf': bool(args.includeuserdefinedlogs)}

        start_date_time = (datetime.fromisoformat(args.startdatetime)
                           .astimezone(timezone.utc))
        end_date_time = (datetime.fromisoformat(args.enddatetime)
                         .astimezone(timezone.utc))

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

        print(f'Locating Virtual Service {vs_name}...')

        vs_obj = api.get_object_by_name('virtualservice', name=vs_name,
                                        tenant=tenant,
                                        params={'fields': 'uuid'})

        if not vs_obj:
            print(f'Unable to locate Virtual Service "{vs_name}"')
            exit()

        params['virtualservice'] = vs_obj['uuid']
        params['download'] = True
        params['page_size'] = 1
        params['duration'] = 1
        params['query_id'] = int(100*datetime.now().timestamp())

        print('>> Retrieving log field names...')
        r = api.get('analytics/logs', tenant=tenant, params=params)
        if r.status_code == 200:
            field_names = r.text.splitlines(False)[0].split(',')

        print(f'  Found {len(field_names)} fields.')

        params['start'] = start_date_time.isoformat(timespec='milliseconds')
        params['download'] = False
        params['format'] = 'json'
        params['page_size'] = 10000
        params['page'] = 1
        params.pop('duration', None)

        total_logs = 0

        print(f':: Writing to file {filename}...')

        with (open(filename, 'w', newline='')) as csv_file:
            csv_writer = csv.writer(csv_file, dialect='excel')
            csv_writer.writerow(field_names)

            while True:
                print(f'>> Retrieving up to 10,000 logs from '
                      f'{start_date_time:%c %Z} to '
                      f'{end_date_time:%c %Z}...')

                params['end'] = end_date_time.isoformat(timespec='milliseconds')
                params['query_id'] = int(100*datetime.now().timestamp()),

                r = api.get('analytics/logs', tenant=tenant, params=params)
                if r.status_code == 200:
                    r_data = r.json()
                    results = r_data['results']
                    res_count = len(results)
                    """
                    Note that we cannot assume that r_data['count'] indicates
                    the actual number of logs present in the time interval
                    as the Controller may still be indexing the logs. The API
                    call returns once there are 10,000 results available to be
                    returned even if there are more logs to be indexed. Hence we
                    keep iterating until we actually get no more results.
                    """

                    if res_count > 0:
                        print(f'  Got {res_count} logs')
                        for res in results:
                            vals = ["'" + str(v) if v is not None and
                                    str(v).lstrip().startswith(('+', '-', '='))
                                    else v for v in [res.get(f, None)
                                                     for f in field_names]]
                            csv_writer.writerow(vals)
                        total_logs += res_count
                        last_entry = results[-1]['report_timestamp']
                        end_date_time = datetime.fromisoformat(last_entry)
                    else:
                        print(f':: No further logs were found')
                        break
                else:
                    break
        print(f'{total_logs} logs were retrieved.')
    else:
        parser.print_help()
