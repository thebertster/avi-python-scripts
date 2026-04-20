#!/usr/bin/env python

"""Script to export and correlate Controller Patch Event Logs to a CSV file."""

import argparse
import csv
import getpass
import json
import re  
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


def extract_patch_data(event_id, details):
    """Extracts specific fields into a dictionary for separate CSV columns."""
    extracted = {
        'patch_ids': '',
        'request_data': '',
        'status': '',
        'error_message': ''
    }

    if not details or not isinstance(details, dict):
        return extracted

    # Target the exact payload block
    patch_state = details.get('async_patch_state', {})

    if event_id == 'ASYNC_PATCH_STATUS':
        extracted['request_data'] = patch_state.get('request_data', '').strip()
        extracted['patch_ids'] = str(patch_state.get('patch_ids', ''))

    elif event_id == 'MERGED_ASYNC_PATCH_STATUS':
        extracted['status'] = patch_state.get('status', '')
        extracted['patch_ids'] = str(patch_state.get('patch_ids', ''))
        
        # Check if the status indicates a failure
        if extracted['status'] and str(extracted['status']).lower() in ['fail', 'failed', 'error']:
            extracted['error_message'] = patch_state.get('error_message', '')

    return extracted


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
    
    parser.add_argument('startdatetime',
                        help='Start date and time for exported logs '
                             'in ISO8601 format, e.g. 2024-01-01T00:00.')
    parser.add_argument('enddatetime',
                        help='Start date and time for exported logs '
                             'in ISO8601 format, e.g. 2024-01-01T00:00.')

    args = parser.parse_args()

    if args:
        controller = args.controller
        user = args.user
        password = args.password
        tenant = args.tenant
        api_version = args.apiversion
        filename = args.filename or devnull

        start_date_time = (datetime.fromisoformat(args.startdatetime)
                           .astimezone(timezone.utc))
        end_date_time = (datetime.fromisoformat(args.enddatetime)
                         .astimezone(timezone.utc))

        while not controller:
            controller = input('Controller:')

        while not password:
            password = getpass.getpass(f'Password for {user}@{controller}:')

        if not api_version:
            api = ApiSession.get_session(controller, user, password)
            api_version = api.remote_api_version['Version']
            api.delete_session()
            print(f'Discovered Controller version {api_version}.')
            
        api = ApiSession.get_session(controller, user, password,
                                     api_version=api_version)

        field_names = ['report_timestamp', 'obj_type', 'event_id',
                       'module', 'internal', 'context', 'obj_uuid',
                       'obj_name', 'patch_ids', 'status', 'error_message', 'request_data']

        params = {
            'page_size': 10000,
            'page': 1,
            'type': 2,
            'start': start_date_time.isoformat(timespec='microseconds'),
            'end': end_date_time.isoformat(timespec='microseconds'),
            'format': 'json',
            'filter': 'co(event_details,async_patch_state)'
        }

        # Data structures for our Correlation Engine
        status_map = {}
        all_target_events = []
        raw_events_fetched = 0

        print(f':: Fetching logs from {start_date_time:%c %Z} to {end_date_time:%c %Z}...')

        # --- PHASE 1: COLLECT AND MAP ---
        while end_date_time is not None:
            params['query_id'] = get_query_id()
            params['end'] = end_date_time.isoformat(timespec='microseconds')

            r = api.get('analytics/logs', tenant=tenant, params=params)
            if r.status_code == 200:
                r_data = r.json()
                results = r_data.get('results', [])
                res_count = len(results)

                if res_count > 0:
                    ts_first = datetime.fromisoformat(results[0]['report_timestamp'])
                    ts_last = datetime.fromisoformat(results[-1]['report_timestamp'])

                    if ts_first == ts_last:
                        ts_last = None
                    else:
                        check = 1
                        while True:
                            ts_check = datetime.fromisoformat(results[-check-1]['report_timestamp'])
                            if ts_check == ts_last:
                                check += 1
                            else:
                                break
                        results = results[:-check]
                        res_count -= check

                    raw_events_fetched += res_count
                    
                    for res in results:
                        current_event_id = res.get('event_id', '')
                        
                        if current_event_id not in ['ASYNC_PATCH_STATUS', 'MERGED_ASYNC_PATCH_STATUS']:
                            continue
                            
                        # Extract the data
                        parsed = extract_patch_data(current_event_id, res.get('event_details', {}))
                        raw_p_ids_string = parsed.get('patch_ids', '')
                        
                        # Use regex to find all distinct IDs, ignoring brackets/quotes/commas
                        individual_ids = re.findall(r'[a-zA-Z0-9_-]+', raw_p_ids_string)
                        
                        # Process MERGED events: map status to EVERY ID in the list
                        if current_event_id == 'MERGED_ASYNC_PATCH_STATUS':
                            for p_id in individual_ids:
                                status_map[p_id] = {
                                    'status': parsed.get('status', ''),
                                    'error_message': parsed.get('error_message', '')
                                }
                            all_target_events.append({**res, **parsed})
                        
                        # Process ASYNC events: store the clean single ID for later lookup
                        elif current_event_id == 'ASYNC_PATCH_STATUS':
                            # Even if there's only one, regex ensures we get it cleanly without quotes
                            parsed['clean_patch_id'] = individual_ids[0] if individual_ids else None
                            all_target_events.append({**res, **parsed})
                            
                    end_date_time = ts_last
                    print(f'  Fetched batch of {res_count} logs (sliding window...)')
                else:
                    end_date_time = None
            else:
                print(f':: Error {r.status_code} {r.text} occurred: giving up!')
                break

        print(f':: Finished fetching. Correlating statuses for {len(all_target_events)} events...')

        # --- PHASE 2: CORRELATE AND WRITE TO CSV ---
        print(f':: Writing correlated data to {filename}...')
        written_count = 0
        
        with open(filename, 'w', newline='', encoding='UTF-8') as csv_file:
            csv_writer = csv.writer(csv_file, dialect='excel')
            csv_writer.writerow(field_names)

            for event in all_target_events:
                current_event_id = event.get('event_id', '')
                
                # Look up the status using the clean individual ID
                if current_event_id == 'ASYNC_PATCH_STATUS':
                    clean_p_id = event.get('clean_patch_id')
                    
                    if clean_p_id and clean_p_id in status_map:
                        # Happy path: We found the matching MERGED event
                        event['status'] = status_map[clean_p_id]['status']
                        event['error_message'] = status_map[clean_p_id]['error_message']
                    else:
                        # BUG CATCHER: No MERGED event was ever found for this patch ID!
                        event['status'] = 'FAILED (SILENT BUG)'
                        event['error_message'] = 'No MERGED event generated by ALB. Assumed failed due to known bug.'
                
                # Build the row
                row_vals = []
                for f in field_names:
                    val = event.get(f, '')
                    
                    if val is not None and str(val).lstrip().startswith(('+', '-', '=')):
                        val = "'" + str(val)
                        
                    row_vals.append(val)
                    
                csv_writer.writerow(row_vals)
                written_count += 1
                
        print(f':: Success! {written_count} target events written to CSV.')

    else:
        parser.print_help()