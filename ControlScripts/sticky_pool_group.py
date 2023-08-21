#!/usr/bin/python3
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

def ParseAviParams(argv):
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
    query = 'refers_to=pool:%s' % pool_uuid
    pg_result = session.get('poolgroup', params=query)
    if pg_result.count() == 0:
        return 'No pool group found referencing pool %s' % pool_name

    pg_obj = pg_result.json()['results'][0]

    highest_up_pool = None
    highest_down_pool = None

    for member in pg_obj['members']:
        priority_label = member['priority_label']
        member_ref = member['pool_ref']
        pool_runtime_url = ('%s/runtime/detail' %
                            member_ref.split('/api/')[1])
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
        return ('No action required. The highest-priority available '
                'pool (%s) already has a higher priority than the '
                'highest-priority non-available pool (%s)' %
                (highest_up_pool[2], highest_down_pool[2]))

    highest_up_pool[0]['priority_label'] = highest_down_pool[1]
    highest_down_pool[0]['priority_label'] = highest_up_pool[1]

    p_result = session.put('poolgroup/%s' % pg_obj['uuid'], pg_obj)
    if p_result.status_code < 300:
        return ', '.join(['Pool %s priority changed to %s' % (p[0], p[1])
                          for p in ((highest_up_pool[2], highest_down_pool[1]),
                                    (highest_down_pool[2], highest_up_pool[1]))
                          ])
    if p_result.status_code == 412:
        return failover_pools(session, pool_uuid, pool_name, retries - 1)

    return 'Error setting pool priority: %s' % p_result.text

if __name__ == "__main__":
    alert_params = ParseAviParams(sys.argv)
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
