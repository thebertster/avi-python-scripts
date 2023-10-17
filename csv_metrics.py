#!/usr/bin/env python

import argparse
import csv
import getpass
from datetime import datetime

import requests
import urllib3
from avi.sdk.avi_api import ApiSession
from tabulate import tabulate

# Disable certificate warnings

if hasattr(requests.packages.urllib3, 'disable_warnings'):
    requests.packages.urllib3.disable_warnings()

if hasattr(urllib3, 'disable_warnings'):
    urllib3.disable_warnings()

SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 60 * SECONDS_PER_MINUTE
SECONDS_PER_DAY = 24 * SECONDS_PER_HOUR

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
    parser.add_argument('-v', '--virtualservice', help='Virtual Service Name')
    parser.add_argument('-m', '--metrics',
                        help='Comma-separated list of metric Ids',
                        default='l4_client.avg_rx_bytes,l4_client.avg_tx_bytes')
    parser.add_argument('-g', '--granularity',
                        help='Granularity of metrics',
                        choices=['realtime','5min','hour','day'],
                        default='5min')
    parser.add_argument('-e', '--end',
                        help='End date/time for metrics in ISO8601 '
                             'format (default=now)')
    parser.add_argument('-l', '--history',
                        help='Timespan of metrics in seconds or append '
                             'm(inutes), h(ours) or d(ays)',
                             default='60m')
    parser.add_argument('-f', '--file', help='Output to named CSV file ')

    args = parser.parse_args()

    granularity_to_seconds = {'realtime': 5, '5min': 5 * SECONDS_PER_MINUTE,
                              'hour': SECONDS_PER_HOUR,
                              'day': SECONDS_PER_DAY}

    if args:
        # If not specified on the command-line, prompt the user for the
        # controller IP address and/or password

        controller = args.controller
        user = args.user
        password = args.password
        tenant = args.tenant
        api_version = args.apiversion
        vs = args.virtualservice
        metrics = args.metrics.split(',')
        granularity = granularity_to_seconds[args.granularity]
        end = datetime.isoformat(datetime.fromisoformat(args.end)
                                 if args.end else datetime.utcnow())
        history = args.history
        csv_filename = args.file

        if history[-1] == 'm':
            history = int(history[:-1]) * SECONDS_PER_MINUTE
        elif history[-1] == 'h':
            history = int(history[:-1]) * SECONDS_PER_HOUR
        elif history[-1] == 'd':
            history = int(history[:-1]) * SECONDS_PER_DAY
        else:
            history = int(history)

        limit = history // granularity

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

        vs = api.get_object_by_name('virtualservice', vs, tenant=tenant)

        if not vs:
            print(f'Unable to locate Virtual Service "{vs}"')
            exit()

        vs_uuid = vs['uuid']

        params = {'stop': end, 'step': granularity, 'limit': limit,
                  'metric_id': ','.join(metrics)}

        metrics = api.get(f'analytics/metrics/virtualservice/{vs_uuid}',
                          params=params, tenant=tenant).json()

        series = metrics['series']

        headers = ['Timestamp']
        output = {}

        for metric in series:
            metric_name = metric['header']['name']
            metric_unit = metric['header']['units']
            headers.append(f'{metric_name} in {metric_unit}')
            data = metric['data']
            for data_point in data:
                timestamp = data_point['timestamp']
                if timestamp not in output:
                    output[timestamp] = []
                output[timestamp].append(data_point['value'])

        output_table = [[k, *output[k]] for k in sorted(output)]


        if csv_filename:
            print(f'Outputting data to {csv_filename}')
            with open(csv_filename, 'w', newline='') as csv_file:
                csv_writer = csv.writer(csv_file, dialect='excel')
                csv_writer.writerow(headers)
                csv_writer.writerows(output_table)
        else:
            print(tabulate(output_table, headers=headers, tablefmt='outline'))

    else:
        parser.print_help()
