#!/usr/bin/python3

"""This ControlScript Automatically adjusts Pool priorities for a Pool Group
to prevent automatic fail-back. This ControlScript is largely superceded by
the deactivate_primary_pool_on_down feature."""

import os
import sys
import json
from avi.sdk.avi_api import ApiSession
import urllib3
import requests

if hasattr(requests.packages.urllib3, 'disable_warnings'):
    requests.packages.urllib3.disable_warnings()

if hasattr(urllib3, 'disable_warnings'):
    urllib3.disable_warnings()


def parse_avi_params(argv):
    if len(argv) != 2:
        return
    alert_params = json.loads(argv[1])
    print(str(alert_params))
    return alert_params


def get_api_token():
    return os.environ.get('API_TOKEN')


def get_api_user():
    return os.environ.get('USER')


def get_api_endpoint():
    return os.environ.get('DOCKER_GATEWAY') or 'localhost'


def get_tenant():
    return os.environ.get('TENANT')


def failover_pools(session, pool_uuid, pool_name, retries=5):
    if retries <= 0:
        return 'Too many retry attempts - aborting!'
    query = f'refers_to=pool:{pool_uuid}'
    pg_result = session.get('poolgroup', params=query)
    if pg_result.count() == 0:
        return f'No pool group found referencing pool {pool_name}'

    pg_obj = pg_result.json()['results'][0]
    pg_uuid = pg_obj['uuid']

    highest_up_pool = ()
    highest_down_pool = ()

    for member in pg_obj['members']:
        priority_label = member['priority_label']
        member_ref = member['pool_ref']
        pool_uuid = member_ref.split('/api/')[1]
        pool_runtime_url = f'{pool_uuid}/runtime/detail'
        pool_obj = session.get(pool_runtime_url).json()[0]
        if pool_obj['oper_status']['state'] == 'OPER_UP':
            if (not highest_up_pool or
                    int(highest_up_pool[1]) < int(priority_label)):
                highest_up_pool = (member, priority_label,
                                   pool_obj['name'])
        elif (not highest_down_pool or
              int(highest_down_pool[1]) < int(priority_label)):
            highest_down_pool = (member, priority_label,
                                 pool_obj['name'])

    if not highest_up_pool:
        return ('No action required as all pools in the '
                'pool group are now down.')
    elif not highest_down_pool:
        return ('No action required as all pools in the '
                'pool group are now up.')

    if int(highest_down_pool[1]) <= int(highest_up_pool[1]):
        return (f'No action required. The highest-priority available pool '
                f'({highest_up_pool[2]}) has a higher priority than the '
                f'highest-priority non-available pool ({highest_down_pool[2]})')

    highest_up_pool[0]['priority_label'] = highest_down_pool[1]
    highest_down_pool[0]['priority_label'] = highest_up_pool[1]

    p_result = session.put(f'poolgroup/{pg_uuid}', pg_obj)
    if p_result.status_code < 300:
        return ', '.join([f'Pool {p[0]} priority changed to {p[1]}'
                          for p in ((highest_up_pool[2], highest_down_pool[1]),
                                    (highest_down_pool[2], highest_up_pool[1]))
                          ])
    if p_result.status_code == 412:
        return failover_pools(session, pool_uuid, pool_name, retries - 1)

    return f'Error setting pool priority: {p_result.text}'


if __name__ == '__main__':
    alert_params = parse_avi_params(sys.argv)
    events = alert_params.get('events', [])
    if len(events) > 0:
        token = get_api_token()
        user = get_api_user()
        api_endpoint = get_api_endpoint()
        tenant = get_tenant()

        pool_uuid = events[0]['obj_uuid']
        pool_name = events[0]['obj_name']
        event_id = events[0]['event_id']
        try:
            with ApiSession(api_endpoint, user,
                            token=token,
                            tenant=tenant) as session:
                result = failover_pools(session, pool_uuid, pool_name)
        except Exception as e:
            result = str(e)
    else:
        result = 'No event data for ControlScript'

    print(result)
