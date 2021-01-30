# Copyright 2020 VMware, Inc.  All rights reserved. -- VMware Confidential
# Description: utility module for service mesh performance
# Disabled: True

import subprocess
import time
import re
from kubernetes import client, config
from constants import *
import requests
import json
from requests.exceptions import ReadTimeout, HTTPError
import random, string


def run_local_sh_cmd(cmd, cwd=None):
    ps = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          close_fds=True, cwd=cwd, bufsize=-1)
    out = ''
    err = ''
    while True:
        line = ps.stdout.readline()
        if not line:
            break
        out += line.decode("utf-8")
    while True:
        line = ps.stderr.readline()
        if not line:
            break
        err += line.decode("utf-8")
    status = ps.wait()
    return status, out, err

def request(url, data=None, operation='', csp_url=None,
                headers=None,
                status_code=[200], is_json=True,
                status_code_exception=True, timeout=300,
                ignore_error=False, verbose_flag=False,
                csp=None):
    if len(operation) == 0:
        raise Exception('Operation could not be empty.')
    if verbose_flag:
        print('URL: %s' % url)
    if not headers:
        headers = {}
    if is_json and data:
        if verbose_flag:
            print('JSON post')
        data = json.dumps(data)
        if 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/json'
    if verbose_flag:
        print('Data: %s' % str(data))
        print('Headers: %s' % str(headers))
    i = 0
    start_time = time.time()
    while True:
        try:
            if operation == 'POST':
                if not data:
                    req = requests.post(url, verify=True,
                                        headers=headers,
                                        timeout=timeout)
                else:
                    req = requests.post(url, data=data, verify=True,
                                        headers=headers,
                                        timeout=timeout)
            elif operation == 'PUT':
                if not data:
                    req = requests.put(url, verify=True, headers=headers,
                                   timeout=timeout)
                else:
                    req = requests.put(url, data=data, verify=True,
                                       headers=headers,
                                       timeout=timeout)
            elif operation == 'GET':
                req = requests.get(url, verify=True, headers=headers,
                                   timeout=timeout)
            elif operation == 'DELETE':
                if not data:
                    req = requests.delete(url, verify=True,
                                          headers=headers,
                                          timeout=timeout)
                else:
                    req = requests.delete(url, data=data, verify=True,
                                          headers=headers,
                                          timeout=timeout)
            else:
                raise Exception('unsupported {}'.format(operation))
            if verbose_flag:
                print('{} {}'.format(req.text, req.status_code))
            if req.status_code == 401:
                access_token = csp.refresh_access_token()
                headers['csp-auth-token'] = '{}'.format(access_token)
                continue
            if status_code_exception and req.status_code not in status_code:
                if status_code_exception and (500 <= req.status_code < 600):
                    req.raise_for_status()
            break
        except requests.exceptions.SSLError:
            raise
        except (requests.ConnectionError, ReadTimeout,
                requests.TooManyRedirects, requests.Timeout,
                HTTPError) as ex:
            if ignore_error:
                return
            i += 1
            if i >= 4:
                raise
            print(ex)
            pass
    else:
        raise AssertionError('{} request failed'.format(operation))
    if verbose_flag:
        print('Reason: %s' % req.reason)
        print('Status code: %s' % req.status_code)
    if status_code_exception and req.status_code not in status_code:
        if verbose_flag:
            print('Text: %s' % req.text)
        raise AssertionError('Reason %s Text: %s' % (req.reason, req.text))
    print("\n\napi {} {}\n------ {} seconds ------\n\n".format(operation, url, (time.time() - start_time)))
    return req

def generate_randoms(length=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k = length))

class CSP(object):

    def __init__(self, refresh_token, log=None):
        self.refresh_token = refresh_token
        self.access_token = None
        self.log = log

    def get_access_token(self):
        if self.access_token:
            return self.access_token
        self.refresh_access_token()
        return self.access_token 

    def refresh_access_token(self):
        try:
            url = '{}/csp/gateway/am/api/auth/api-tokens/'\
            'authorize?refresh_token={}'.format(STAGING_CSP_URL, self.refresh_token)
            resp = request(url, operation='POST').json()
            self.access_token = resp['access_token']
            return self.access_token
        except Exception as e:
            raise

def wait_while_populating_to_tsm(pod_num):
    if pod_num > 100:
        time.sleep(60 * 5)
    else:
        time.sleep(60 * 3)

def is_token_expiring(threshold):
    """
    Decode the Auth token and check the expiration.
    Verify if the time to expire the Auth token is less than the threshold
    return:
    0 not expired
    1 expired or none existing, need refresh
    """
    access_token = state.get_csp_access_token()
    if access_token is None:
        return 1
    try:
        # Decode the Auth token. Skip verification.
        # This will still validate the token claims i.e. expired token etc
        payload = jwt.decode(access_token, verify=False)
        exp = payload['exp']
        if not exp:
            return 0
        currtime = calendar.timegm(datetime.utcnow().utctimetuple())
        time_elapsed = currtime - payload['iat']
        print('Auth token issued at %s expiration timestamp: %s Curr time: %s'
              % (payload['iat'], exp, currtime))
        time_remaining = 1800 - time_elapsed
        if not threshold:
            threshold = 6
        else:
            threshold = int(threshold)
        if time_remaining <= threshold:
            print("need refresh access token.")
            return 1
    except jwt.InvalidTokenError:
        # Ignore any token validation error
        return 1
    print("access token is not expired yet.")
    return 0

