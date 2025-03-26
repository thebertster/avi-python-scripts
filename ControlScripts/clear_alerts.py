#!/usr/bin/python3
import os
import json
import sys
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


def clear_vs_down_alerts(session, vs_uuid):
    print(vs_uuid)
    rsp = session.get(f'alert/?obj_ref={vs_uuid}&search=(event_id,VS_DOWN)')
    if rsp.status_code != 200:
        print('Could not find any alerts to clear')
        return

    vs_down_alerts = json.loads(rsp.content)

    for alert in vs_down_alerts['results']:
        alert_uuid = alert['uuid']
        print(f'Clearing alert {alert_uuid}')
        session.delete(f'alert/{alert_uuid}')


if __name__ == '__main__':
    alert_params = parse_avi_params(sys.argv)
    for event in alert_params.get('events', []):
        if event['event_id'] == 'VS_UP':
            vs_uuid = event['obj_uuid']
            break

    if vs_uuid:
        token = get_api_token()
        user = get_api_user()
        api_endpoint = get_api_endpoint()
        tenant = get_tenant()

        with ApiSession(api_endpoint, user, token=token,
                        tenant=tenant if tenant != 'admin' else '*') as session:
            clear_vs_down_alerts(session, vs_uuid)
    else:
        print('No VS_UP Event found in alert data')
