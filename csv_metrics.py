#!/usr/bin/env python

"""Script to display metrics in a simple table or to export metrics data
to a CSV file."""

import argparse
import csv
import getpass
from datetime import datetime, timezone

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
                        help='FQDN or IP address of Avi Controller')
    parser.add_argument('-u', '--user', help='Avi API Username',
                        default='admin')
    parser.add_argument('-p', '--password', help='Avi API Password')
    parser.add_argument('-t', '--tenant', help='Tenant',
                        default='admin')
    parser.add_argument('-x', '--apiversion', help='Avi API version')
    parser.add_argument('-m', '--metrics',
                        help='Comma-separated list of metric Ids',
                        default='l4_client.avg_rx_bytes,l4_client.avg_tx_bytes')
    parser.add_argument('-g', '--granularity',
                        help='Granularity of metrics',
                        choices=['realtime', '5min', 'hour', 'day'],
                        default='5min')
    parser.add_argument('-e', '--end',
                        help='End date/time for metrics in ISO8601 '
                             'format (default=now)')
    parser.add_argument('-l', '--history',
                        help='Timespan of metrics in seconds or append '
                             'm(inutes), h(ours) or d(ays)',
                             default='60m')
    parser.add_argument('-se', '--serviceengine', help='Service Engine Name')
    parser.add_argument('-vs', '--virtualservice',
                        help='Virtual Service Name')
    parser.add_argument('-a', '--aggregate',
                        help='Aggregate metrics', action='store_true')
    parser.add_argument('-pl', '--pool',
                        help='Pool Name')
    parser.add_argument('-f', '--file', help='Output to named CSV file')
    parser.add_argument('-o', '--objid',
                        help='Optional object ID - required for metrics that '
                             'relate to specific components such as WAF rule '
                             'or WAF group metrics')
    parser.add_argument('-ao', '--aggregateobjid',
                        help='Aggregate object IDs', action='store_true')
    parser.add_argument('-pd', '--paddata',
                        help='Pad missing data in the output',
                        action='store_true')

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
        pool = args.pool
        se = args.serviceengine
        aggregate = args.aggregate
        agg_objid = args.aggregateobjid
        metrics = args.metrics.split(',')
        granularity = granularity_to_seconds[args.granularity]
        end = datetime.isoformat(datetime.fromisoformat(args.end)
                                 if args.end else datetime.now(timezone.utc))
        history = args.history
        csv_filename = args.file
        obj_id = args.objid
        pad_data = args.paddata

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

        if se:
            se_obj = api.get_object_by_name('serviceengine', se, tenant=tenant)

            if not se_obj:
                print(f'Unable to locate Service Engine "{se}"')
                exit()

        if pool:
            pool_obj = api.get_object_by_name('pool', pool, tenant=tenant)

            if not pool_obj:
                print(f'Unable to locate Pool "{pool}"')
                exit()

        if vs:
            vs_obj = api.get_object_by_name('virtualservice', vs,
                                            tenant=tenant)

            if not vs_obj:
                print(f'Unable to locate Virtual Service "{vs}"')
                exit()

        # Possible combinations:
        # se only - Retrieve Service Engine Metrics
        # se + aggregate - Aggregated Metrics across SE
        # vs only - Retrieve Metrics for specified Virtual Service
        # pool only - Retrive Metrics for specified Pool
        # vs + pool - Retrieve Metrics for specified Virtual Service and Pool

        params = {'stop': end, 'step': granularity, 'limit': limit,
                  'metric_id': ','.join(metrics),
                  'pad_missing_data': pad_data}

        if se and not(vs or pool):
            if aggregate:
                params['aggregate_entity'] = True
                params['entity_uuid'] = '*'
                params['service_engine_uuid'] = se_obj['uuid']
            else:
                params['entity_uuid'] = se_obj['uuid']
        elif vs and not(se or pool):
            params['entity_uuid'] = vs_obj['uuid']
        elif pool and not(vs or se):
            params['entity_uuid'] = pool_obj['uuid']
        elif not(se) and vs and pool:
            params['entity_uuid'] = vs_obj['uuid']
            params['pool_uuid'] = pool_obj['uuid']
        else:
            print('Unsupported combination of options')
            exit()

        if obj_id:
            params['obj_id'] = obj_id
            if agg_objid:
                params['aggregate_obj_id'] = True

        data = {'metric_requests': [params]}

        metrics = api.post('analytics/metrics/collection',
                           data=data, tenant=tenant).json()

        series_data = metrics.get('series', {})

        num_series = len(series_data)

        if num_series == 0:
            print('No data was returned - did you get a parameter wrong?')
            exit()

        for index, (series_name, series) in enumerate(series_data.items()):
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
                print(f'Writing to {csv_filename} for series {series_name}')
                with open(csv_filename, 'a' if index else 'w',
                          newline='', encoding='UTF-8') as csv_file:
                    csv_writer = csv.writer(csv_file, dialect='excel')
                    if num_series > 1:
                        csv_writer.writerow([series_name])
                    csv_writer.writerow(headers)
                    csv_writer.writerows(output_table)
            else:
                print()
                print(f'Series {series_name}:')
                print(tabulate(output_table, headers=headers,
                            tablefmt='outline'))
    else:
        parser.print_help()
