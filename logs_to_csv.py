#!/usr/bin/env python

import argparse
import csv
import getpass
import time
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

def get_query_id():
    return int(100*datetime.now().timestamp())

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
    parser.add_argument('-fs', '--filterstring', help='Filter String',
                        action='append')
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
        filterstrings = args.filterstring

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

        # First, we make a dummy request for logs using the "download" option
        # which returns a CSV file from which we can extract the column headers
        # which will be the set of valid log field names as these will vary
        # depending on software version.

        params['virtualservice'] = vs_obj['uuid']
        params['download'] = True
        params['page_size'] = 1
        params['page'] = 1
        params['duration'] = 1
        params['query_id'] = get_query_id()

        print(':: Retrieving log field names...')
        r = api.get('analytics/logs', tenant=tenant, params=params)
        if r.status_code == 200:
            field_names = r.text.splitlines(False)[0].split(',')
        else:
            print('  Unable to obtain log field names : giving up!')
            exit()

        print(f'  Found {len(field_names)} fields.')

        params['start'] = start_date_time.isoformat(timespec='milliseconds')
        params['end'] = end_date_time.isoformat(timespec='milliseconds')
        params['download'] = False
        params['format'] = 'json'
        params.pop('duration', None)

        # Next, we need to wait for the logs to be fully indexed.
        # We do this by repeatedly requesting the logs for the entire
        # requested time range but only asking for a single log entry.
        # The Controller will return the data including a percent_remaining
        # field which indicates the percentage of logs within the requested
        # date range remain to be indexed. We keep looping, with a delay
        # proportional to percent_remaining until percent_remaining == 0.

        print(':: Making sure logs have been indexed...')

        while True:
            params['query_id'] = get_query_id()

            r = api.get('analytics/logs', tenant=tenant, params=params)
            if r.status_code == 200:
                r_data = r.json()
                percent_remaining = r_data['percent_remaining']
                if percent_remaining == 0.0:
                    print('  Logs are indexed')
                    break

                print(f'  Logs are being indexed : '
                      f'{percent_remaining}% remaining...')
                time.sleep(percent_remaining / 10)
            else:
                print('  Error while waiting for log indexing : giving up!')
                exit()

        # Now that the logs are indexed, we can iteratively retrieve all
        # the required logs from the entire requested time range.

        if filterstrings:
            params['filter'] = filterstrings
        params['page_size'] = 10000

        total_logs = 0

        print(f':: Writing to file {filename}...')

        with (open(filename, 'w', newline='', encoding='UTF-8')) as csv_file:
            csv_writer = csv.writer(csv_file, dialect='excel')
            csv_writer.writerow(field_names)

            while True:
                print(f':: Retrieving up to 10,000 logs from '
                      f'{start_date_time:%c %Z} to '
                      f'{end_date_time:%c %Z}...')

                params['query_id'] = get_query_id()
                params['end'] = end_date_time.isoformat(timespec='milliseconds')

                r = api.get('analytics/logs', tenant=tenant, params=params)
                if r.status_code == 200:
                    r_data = r.json()
                    results = r_data['results']
                    res_count = len(results)

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
                        print(':: No more logs available')
                        break
                else:
                    print(f':: Error {r.status_code} occurred : giving up!')
                    break
        print(f':: {total_logs} logs were retrieved')
    else:
        parser.print_help()
