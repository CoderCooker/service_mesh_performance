# Copyright 2020 VMware, Inc.  All rights reserved. -- VMware Confidential
# Description: config module for service mesh performance
# Group-pods-st: optional
# Disabled: false
# Timeout: 24000

from library.utils import *
from library.constants import *
import sys
import traceback
from library.utils import CSP, request
import requests

from six.moves import urllib
import json
import ssl
import os

class GraphQLClient(object):
    def __init__(self, endpoint):
        self.endpoint = endpoint
        self.token = None
        self.headername = None

    def execute(self, query, variables=None):
        return self._send(query, variables)

    def inject_token(self, token, headername='Authorization'):
        self.token = token
        self.headername = headername

    def _send(self, query, variables):
        ssl._create_default_https_context = ssl._create_unverified_context
        data = {'query': query,
                'variables': variables}
        headers = {'Accept': 'application/json',
                   'Content-Type': 'application/json'}

        if self.token is not None:
            headers[self.headername] = '{}'.format(self.token)

        req = urllib.request.Request(self.endpoint, json.dumps(data).encode('utf-8'), headers)

        try:
            response = urllib.request.urlopen(req)
            return response.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            if 'Invalid token' in e.read():
                cmd = 'curl -X POST https://console-stg.cloud.vmware.com/csp/gateway/am/api/auth/api-tokens/authorize?refresh_token={} | jq -r \'.access_token\''.format(self.token)
                rt, out, err = run_local_sh_cmd(cmd)
                assert rt == 0, "Failed updating expired token rt {}, err {}".format(rt, err)
                access_token = out.strip()
                self.inject_token(access_token, headername='csp-auth-token')

                headers[self.headername] = '{}'.format(self.token)
                response = urllib.request.urlopen(req)
                return response.read().decode('utf-8')
            print((e.read()))
            print('')
            raise e

def execute_query(graph_cli, query, variables=None, log=None, return_content=False):
        try:
            start_time = time.time()
            resp = graph_cli._send(query, variables)
            cost = time.time() - start_time
            #log.info("\n\nGRAPHQL  {}------ {} seconds ------\n\n".format(query, cost))
            if return_content == True:
                return resp
            return cost
        except Exception as e:
            traceback.format_exc()
            raise

def Run(args):
    args.log.info("start testing %s"%(args.shortName))
    client_cluster = os.getenv("CLIENT_CLUSTER") if os.getenv("CLIENT_CLUSTER") else args.opts.clientCluster
    csp_token = os.getenv("CSP_TOKEN") if os.getenv("CSP_TOKEN") else args.opts.cspToken
    loop = os.getenv("ITERATION")
    if len(loop) > 0:
        loop = int(loop.strip())
    time_interval = os.getenv("TIME_INTERVAL")

    csp = CSP(csp_token, log=args.log)
    graph_cli = GraphQLClient("{}/graphql".format(STAGING0_API_ENDPOINT))
    try:
        graph_cli.inject_token(csp.get_access_token(), headername='csp-auth-token')
    except Exception as e:
        cmd = 'curl -X POST https://console-stg.cloud.vmware.com/csp/gateway/am/api/auth/api-tokens/authorize?refresh_token={} | jq -r \'.access_token\''.format(csp_token)
        rt, out, err = run_local_sh_cmd(cmd)
        assert rt == 0, "Failed getting refresh token rt {}, err {}".format(rt, err)
        access_token = out.strip()
        graph_cli.inject_token(access_token, headername='csp-auth-token')
        pass
    
    inventory_clusters = "{root{inventory{clusters{name}}}}"
    cost = 0
    for x in range(0, loop):
        cost += execute_query(graph_cli, inventory_clusters,log=args.log)
    cost = cost/loop
    args.log.info("\n\nGRAPHQL  {}------ {} seconds ------\n\n".format(inventory_clusters, cost))
    

    inventory_clusters_serviceinstance = 'query FindServiceInstances($cluster: String, $namespace: String) {root {inventory {clusters(name: $cluster) {domains(name: $namespace) {serviceInstances {name nodeName}}}}}}'
    variables = {
  	 	"cluster": client_cluster,
        "namespace": 'fortioclient'
	 }
    cost = 0
    for x in range(0, loop):
        cost += execute_query(graph_cli, inventory_clusters_serviceinstance,log=args.log)
    cost = cost/loop
    args.log.info("\n\nGRAPHQL  {}------ {} seconds ------\n\n".format(inventory_clusters_serviceinstance, cost))

    inventory_table = 'query clusterInventoryTable($startTime: String, $endTime: String) { root { inventory { clusters { name queryClusterTable(startTime: $startTime, endTime: $endTime) { data __typename } __typename } __typename } __typename}}'
    variables = {
  	 	"startTime": '%s' % (time.time() - 1000),
        "endTime": '%s' % (time.time())
	 }	
    cost = 0
    for x in range(0, loop):
        cost += execute_query(graph_cli, inventory_table, variables=variables, log=args.log)
    cost = cost/loop
    args.log.info("\n\nGRAPHQL  {}------ {} seconds ------\n\n".format(inventory_table, cost))
    
    inventory_cluster_service_metrics = 'query FindServiceMetrics($cluster: String, $startTime: String, $endTime: String) {root {inventory {clusters(name: $cluster) { name queryServiceTable(startTime: $startTime,endTime: $endTime) {data}}}}}'
    variables = {
  	 	"startTime": '%s' % (time.time() - 1000),
        "endTime": '%s' % (time.time()),
        "cluster": client_cluster
    }
    cost = 0
    for x in range(0, loop):
        cost += execute_query(graph_cli, inventory_cluster_service_metrics, variables=variables, log=args.log)
    cost = cost/loop
    args.log.info("\n\nGRAPHQL  {}------ {} seconds ------\n\n".format(inventory_cluster_service_metrics, cost))

    for service_metric_types in ServiceMetricTypes:
        inventory_cluster_domain = '''query FindServiceMetrics($metric: ServiceMetricTypeEnum $cluster: String $domain: String $service: String $startTime: String $endTime: String) 
    {root {inventory {clusters(name: $cluster) {domains(name: $domain) {name services(name: $service) {name queryServiceTS(svcMetric: $metric, startTime: $startTime, endTime: $endTime, timeInterval: "10s") {data} serviceDeployments { serviceInstances { nodeName }}}}
    queryServiceTS(svcMetric: $metric, startTime: $startTime, endTime: $endTime, timeInterval: "10s") {data}}}}}'''
        variables = {
            "metric": service_metric_types,
            "startTime": '%s' % (time.time() - 1000),
            "endTime": '%s' % (time.time()),
            "cluster": client_cluster,
            "domain": "gns-2ns-sc.local",
            "service": "fortioserver"
        }
        execute_query(graph_cli, inventory_cluster_domain, variables=variables, log=args.log)

    inventory_service_topology = '''query FindServiceTopology($cluster: String $domain: String $service: String $startTime: String $endTime: String) {
root {inventory {clusters(name: $cluster) {name domains(name: $domain) {name services(name: $service) {name queryServiceTopology(startTime: $startTime, endTime: $endTime) {data}}}}}}}'''
    variables = {
  	 	"startTime": '%s' % (time.time() - 30),
        "endTime": '%s' % (time.time()),
        "cluster": client_cluster,
        "domain": "gns-2ns-sc.local",
        "service": "fortioserver"
    }
    cost = 0
    for x in range(0, loop):
        cost += execute_query(graph_cli, inventory_service_topology, variables=variables, log=args.log)
    cost = cost/loop
    args.log.info("\n\nGRAPHQL  {}------ {} seconds ------\n\n".format(inventory_service_topology, cost))

    for node_metric_type in NodeMetricTypes :
        inventory_cluster_node_query = '''query FindClusterNodesMetrics($metric: NodeMetricTypeEnum $cluster: String $startTime: String $endTime: String)
        {root {inventory {clusters(name: $cluster) {nodes {name queryNodeTS(nodeMetric: $metric, startTime: $startTime, endTime: $endTime, timeInterval: "10s") {data}}}}}}'''
        variables = {
            "metric": node_metric_type,
            "startTime": '%s' % (time.time() - 30),
            "endTime": '%s' % (time.time()),
            "cluster": client_cluster
        }
        execute_query(graph_cli, inventory_cluster_node_query, variables=variables, log=args.log)

    inventory_cluster_nodetable = 'query GetNodeTable($cluster: String) {root {inventory {clusters(name: $cluster) {queryNodeTable(startTime: "now()-5m", endTime: "now()") {data}}}}}'
    variables = {
        "cluster": client_cluster
    }
    cost = 0
    for x in range(0, loop):
        cost += execute_query(graph_cli, inventory_cluster_nodetable, variables=variables, log=args.log)
    cost = cost/loop
    args.log.info("\n\nGRAPHQL  {}------ {} seconds ------\n\n".format(inventory_cluster_nodetable, cost))

    inventory_cluster_count = 'query GetClusterInventory {root {inventory {queryClusterInventoryCount(startTime: "now()-5m", endTime: "now()", timeInterval: "10s") {data}}}}'
    cost = 0
    for x in range(0, loop):
        cost += execute_query(graph_cli, inventory_cluster_nodetable, log=args.log)
    cost = cost/loop
    args.log.info("\n\nGRAPHQL  {}------ {} seconds ------\n\n".format(inventory_cluster_nodetable, cost))
    
    inventory_cluster_connection = 'query GetClusterConnection($cluster: String) {root {inventory {clusters(name: $cluster) {connected}}}}'
    cost = 0
    for x in range(0, loop):
        cost += execute_query(graph_cli, inventory_cluster_nodetable, log=args.log)
    cost = cost/loop
    args.log.info("\n\nGRAPHQL  {}------ {} seconds ------\n\n".format(inventory_cluster_nodetable, cost))

    inventory_get_cluster = 'query GetClusterUUID($cluster: String) {root {inventory {clusters(name: $cluster) {uuid}}}}'
    variables = {"cluster": client_cluster}
    cost = 0
    for x in range(0, loop):
        cost += execute_query(graph_cli, inventory_get_cluster, variables=variables, log=args.log)
    cost = cost/loop
    args.log.info("\n\nGRAPHQL  {}------ {} seconds ------\n\n".format(inventory_get_cluster, cost))

    inventory_servicets_p50_latency = '{root{inventory{queryServiceTS(svcMetric: p50Latency, startTime:"now()-1h", endTime:"now()", timeInterval:"1m") { data code } } } } '
    cost = 0
    for x in range(0, loop):
        cost += execute_query(graph_cli, inventory_cluster_connection, log=args.log)
    cost = cost/loop
    args.log.info("\n\nGRAPHQL  {}------ {} seconds ------\n\n".format(inventory_cluster_connection, cost))

    gns_config =  '''query ListGlobalNamespaces {root { config {globalNamespace {gns {name}}}}}'''
    cost = 0
    for x in range(0, loop):
        cost += execute_query(graph_cli, gns_config, log=args.log)
    cost = cost/loop
    args.log.info("\n\nGRAPHQL  {}------ {} seconds ------\n\n".format(gns_config, cost))        

    gns_details_query =  '''query GetGlobalNamespace($name: String) {root {config {globalNamespace {gns(name: $name) {
   name description color domain caType  ca version matchingConditions }}}}}'''
    variables = {"name": "fptlxm"}
    cost = 0
    for x in range(0, loop):
        cost += execute_query(graph_cli, gns_details_query, variables=variables, log=args.log)
    cost = cost/loop
    args.log.info("\n\nGRAPHQL  {}------ {} seconds ------\n\n".format(gns_details_query, cost)) 

    gns_service_metrics = 'query FindServiceMetrics($gnsName: String, $startTime: String, $endTime: String) {root {config {globalNamespace {gns(name: $gnsName) {queryServiceInstanceTable(startTime: $startTime, endTime: $endTime) {data}}}}}}'
    variables = {
  	 	"startTime": '%s' % (time.time() - 1000),
        "endTime": '%s' % (time.time()),
        "gnsName": 'fptlxm'
    }
    cost = 0
    for x in range(0, loop):
        cost += execute_query(graph_cli, gns_service_metrics, variables=variables, log=args.log)
    cost = cost/loop
    args.log.info("\n\nGRAPHQL  {}------ {} seconds ------\n\n".format(gns_service_metrics, cost))
