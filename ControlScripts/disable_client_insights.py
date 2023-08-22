#!/usr/bin/python3
import os
import json
from avi.sdk.avi_api import ApiSession
import urllib3
import requests

if hasattr(requests.packages.urllib3, 'disable_warnings'):
    requests.packages.urllib3.disable_warnings()

if hasattr(urllib3, 'disable_warnings'):
    urllib3.disable_warnings()

def get_api_token():
    return os.environ.get('API_TOKEN')

def get_api_user():
    return os.environ.get('USER')

def get_api_endpoint():
    return os.environ.get('DOCKER_GATEWAY') or 'localhost'

if __name__ == "__main__":
    api_endpoint = get_api_endpoint()
    user = get_api_user()
    token = get_api_token()

    with ApiSession(api_endpoint, user, token=token, tenant='*') as session:
        resp = session.get('virtualservice',
                           params={'search': '(client_insights,IVE)',
                                   'fields': 'analytics_policy'})
        if resp.status_code < 300:
            resp_json = resp.json()
            count = resp_json['count']
            if count == 0:
                print('No Virtual Services found with Client Insights enabled')
                exit()
            vs_list = resp_json['results']
            print(f'{count} Virtual Service(s) with Client Insights enabled | ')
            for vs in vs_list:
                vs_name = vs['name']
                vs_uuid = vs['uuid']
                ci_curr = vs['analytics_policy']['client_insights']
                print(f'Virtual Service {vs_name} has CI {ci_curr} >> ')
                data = {
                    'json_patch': [
                        {
                            'op': 'replace',
                            'path': '/analytics_policy/client_insights',
                            'value': 'NO_INSIGHTS'
                        }
                    ]
                }
                upd = session.patch(f'virtualservice/{vs_uuid}',
                                    data=json.dumps(data))
                if upd.status_code < 300:
                    print(f'CI disabled for Virtual Service {vs_name}')
                else:
                    print(f'Failed to disable CI for Virtual Service {vs_name}')
                    print(f'Error: {upd.status_code}: {upd.text}')
                print(' || ')
        else:
            print(f'VS Query returned error: {resp}')
