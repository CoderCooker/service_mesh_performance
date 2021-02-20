# Copyright 2020 VMware, Inc.  All rights reserved. -- VMware Confidential
# Description: config module for service mesh performance
# Group-pods-st: optional
# Disabled: False
# Timeout: 24000

from utils import CSP, request
from constants import *
import sys
import traceback
import random
import string

class GNS(object):

    def __init__(self, csp_token, log=None):
        self.refresh_token = csp_token
        self.csp = CSP(csp_token, log=log)
        self.log = log
    
    
    def create_external_account(self, name, provider_url='https://route53.us-west-2.amazonaws.com'):
        json_payload = {
  "name": name,
  "description": "Account for tsm performance test",
  "provider": "AWS",
  "provider_url": provider_url,
  "authentication_type": "TOKEN",
  "authentication": {
    "auth_token": {
      "access_key": "",
      "secret_access_key": ""
    }
  }
}
        post_url = "{}/external-accounts".format(STAGING0_API_ENDPOINT)
        headers = {'csp-auth-token': self.csp.get_access_token()}
        try:
            resp = request(post_url, data=json_payload,
                          operation='POST',
                          csp_url=STAGING_CSP_URL,
                          status_code=[200], headers=headers,
                          verbose_flag=True).json()
            if self.log:
                self.log.info("successfully creating external-accounts resp {}\n\n".format(resp))
            return resp
        except Exception as e:
            traceback.format_exc()
            raise
    
    def create_external_dns(self, name, external_account_id, provider_url="https://route53.us-west-2.amazonaws.com"):
        json_payload = {"description":"DNS for tsm performance test",
        "dns_type":"GLOBAL",
        "dns_region":"us-west-2",
        "infrastructure_account_id":external_account_id,
        "name":name}
        post_url = "{}/external-domain-name-servers".format(STAGING0_API_ENDPOINT)
        headers = {'csp-auth-token': self.csp.get_access_token()}

        try:
            resp = request(post_url, data=json_payload,
                          operation='POST',
                          csp_url=STAGING_CSP_URL,
                          status_code=[200], headers=headers,
                          verbose_flag=True).json()
            if self.log:
                self.log.info("successfully creating external dns {}\n\n".format(resp))
            return resp
        except Exception as e:
            traceback.format_exc()
            raise

    
    def create_psv(self, gns_id, fqdn, psv_config):
        put_url = '{}/global-namespaces/{}/public-service/{}'.format(STAGING0_API_ENDPOINT, gns_id, fqdn)
        headers = {'csp-auth-token': self.csp.get_access_token()}
        try:
            resp = request(put_url, data=psv_config,
                          operation='PUT',
                          csp_url=STAGING_CSP_URL,
                          status_code=[200, 404], headers=headers,
                          verbose_flag=True).json()
            if self.log:
                self.log.info("successfully creating public service {}\n\n".format(resp))
            return resp
        except Exception as e:
            traceback.format_exc()
            raise

    def config_psv(self, ext_dns_id, gns_name, sub_dom, port=80):
        return {
                  "fqdn": "st-create-http-pub-svc-{}.servicemesh.biz".format(gns_name),
                  "name": gns_name,
                  "external_port": 80,
                  "external_protocol": "HTTP",
                  "ttl": 10,
                  "public_domain": {
                    "external_dns_id": ext_dns_id,
                    "primary_domain": "servicemesh.biz",
                    "sub_domain": sub_dom,
                    "certificate_id": ""
                  },
                  "ha_policy": "",
                  "wildcard_certificate_id": "",
                  "healthcheck_ids": []
                }

    def delete_pvs(self, gns, fqdn):
        headers = {'csp-auth-token': self.csp.get_access_token()}
        del_url = 'https://staging-2.servicemesh.biz/tsm/v1alpha1/global-namespaces/{}/public-service/tsm-perf-http-pub-svc-{}.servicemesh.biz'.format(gns, fqdn)
        try:
            resp = request(del_url,
                          operation='DELETE',
                          csp_url=STAGING_CSP_URL,
                          status_code=[204], headers=headers,
                          verbose_flag=True)
            if self.log:
                self.log.info("successfully deleting public service {}\n\n".format(resp))
            return resp
        except Exception as e:
            traceback.format_exc()
            raise


    def delete(self, gns_name):
        delete_url = "{}/global-namespaces/{}".format(
            STAGING0_API_ENDPOINT, gns_name)
        headers = {'csp-auth-token': self.csp.get_access_token()}
        try:
            request(delete_url, operation='DELETE',
                          status_code=[200, 404, 204],
                          csp_url=STAGING_CSP_URL,
                          headers=headers,
                          verbose_flag=True)
        except Exception as ex:
            traceback.format_exc()
            raise
        if self.log:
            self.log.info("successfully delete gns {}".format(gns_name))
        return 0

    def create(self, namespace_clusters_dict, domain, gns_name=None):
        if not gns_name:
            gns_name = ''.join(random.choices(string.ascii_lowercase + string.digits, k = 6))
        post_url = "{}/global-namespaces/{}".format(
            STAGING0_API_ENDPOINT, gns_name)
        conditions = []
        for cluster in namespace_clusters_dict.keys():
            namespaces = namespace_clusters_dict[cluster]
            for namespace in namespaces:
                conditions.append({
        "namespace": {
          "type": "EXACT",
          "match": "cc-2ns-cls1-ns"
        },
        "cluster": {
          "type": "EXACT",
          "match": "jm-248-cl1-dev-st"
        }
      })
        json_payload = {
            "name": "{}".format(gns_name),
            "display_name": "{}".format(gns_name),
            "domain_name": "{}".format(domain),
            "use_shared_gateway": True,
            "mtls_enforced": True,
            "ca_type": "PreExistingCA",
            "ca": "default",
            "description": "",
            "color": "#007CBB",
            "version": "1.0",
            "match_conditions": conditions
        }
        if self.log:
            self.log.info("to generate gns {}".format(json_payload))

        headers = {'csp-auth-token': self.csp.get_access_token()}

        try:
            request(post_url, data=json_payload,
                          operation='POST',
                          csp_url=STAGING_CSP_URL,
                          status_code=[200], headers=headers,
                          verbose_flag=True)
        except Exception as e:
            traceback.format_exc()
            raise
        if self.log:
            self.log.info("successfully generating gns {}".format(domain))
        return 0

    def save(self, gns_config_dict, domain, gns_name=None):
        if not gns_name:
            gns_name = ''.join(random.choices(string.ascii_lowercase + string.digits, k = 6))
        put_url = "{}/global-namespaces/{}".format(
            STAGING0_API_ENDPOINT, gns_name)
        conditions = []
        for cluster in gns_config_dict.keys():
            namespaces = gns_config_dict[cluster]
            for namespace in namespaces:
                conditions.append({
                    "namespace": {
                    "type": "EXACT",
                    "match": namespace
                    },
                    "cluster": {
                    "type": "EXACT",
                    "match": cluster
                    }
                })

        json_payload = {
                        "name": gns_name,
                        "domain_name": domain,
                        "ca_type": "PreExistingCA",
                        "match_conditions": conditions
                        }
        if self.log:
            self.log.info("to generate gns {}".format(json_payload))

        headers = {'csp-auth-token': self.csp.get_access_token()}

        try:
            request(put_url, data=json_payload,
                          operation='PUT',
                          csp_url=STAGING_CSP_URL,
                          status_code=[200, 400], headers=headers,
                          verbose_flag=True)
        except Exception as e:
            traceback.format_exc()
            raise
        if self.log:
            self.log.info("successfully generating gns {}".format(domain))
        return 0
    
    def list_gns(self):
        list_url = "{}/global-namespaces".format(
            STAGING0_API_ENDPOINT)
        headers = {'csp-auth-token': self.csp.get_access_token()}
        try:
            resp = request(list_url, operation='GET',
                          status_code=[200],
                          csp_url=STAGING_CSP_URL,
                          headers=headers,
                          verbose_flag=True)
            self.log.info('successfully list gns {}'.format(resp.json()))
        except Exception as ex:
            traceback.format_exc()
            raise
        if self.log:
            self.log.info("successfully list gns".format())
        return 0
    
    def get(self, gns_id):
        get_url = "{}/global-namespaces/{}".format(
            STAGING0_API_ENDPOINT, gns_id)
        headers = {'csp-auth-token': self.csp.get_access_token()}
        try:
            resp = request(get_url, operation='GET',
                          status_code=[200],
                          csp_url=STAGING_CSP_URL,
                          headers=headers,
                          verbose_flag=True)
            self.log.info('get gns response {}'.format(resp.json()))
        except Exception as ex:
            traceback.format_exc()
            raise
        if self.log:
            self.log.info("successfully get gns {}".format(gns_id))
        return 0

def Run(args):
    args.log.info("start testing %s" % (args.shortName))
    client_cluster = args.opts.clientCluster
    server_cluster = args.opts.serverCluster
    args.log.debug("CSP Refresh Token")
    gns = GNS(args.opts.cspToken, log=args.log)

    gns.save({client_cluster: [FORTIO_CLIENT_NAMESPACE, FORTIO_SERVER_NAMESPACE]}, GNS_SC_DOMAIN)
    gns.save({client_cluster: [FORTIO_CLIENT_NAMESPACE], server_cluster: [FORTIO_SERVER_NAMESPACE]}, GNS_CC_DOMAIN)
