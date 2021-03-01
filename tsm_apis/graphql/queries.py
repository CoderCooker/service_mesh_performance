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
        args.log.info("loop %s" % (loop))
    args.log.info("client cluster {} CSP_TOKEN {} ITERATION {}".format(client_cluster, csp_token, loop))
    time_interval = os.getenv("TIME_INTERVAL")
    args.log.info("time_interval %s "%(time_interval))
    time_interval = [5, 15, 30, 60]
    test_results = {}

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



    args.log.info("1st query")
    inventory_clusters = "{root{inventory{clusters{name}}}}"
    cost = 0
    for x in range(0, loop):
        cost += execute_query(graph_cli, inventory_clusters,log=args.log)
        args.log.info("loop {} x {} cost {} ".format(loop, x, cost))
    cost = cost/loop
    args.log.info("\n GRAPHQL  {}------ {} seconds ------\n".format(inventory_clusters, cost))
    test_results[inventory_clusters] = cost
    args.log.info("\n\n")
    

    args.log.info("2nd query")
    inventory_clusters_serviceinstance = 'query FindServiceInstances($cluster: String, $namespace: String) {root {inventory {clusters(name: $cluster) {domains(name: $namespace) {serviceInstances {name nodeName}}}}}}'
    variables = {
  	 	"cluster": client_cluster,
        "namespace": 'vmware-system-tsm'
	 }
    cost = 0
    for x in range(0, loop):
        cost += execute_query(graph_cli, inventory_clusters_serviceinstance,log=args.log)
        args.log.info("loop {} x {} cost {} ".format(loop, x, cost))
    cost = cost/loop
    args.log.info("\nGRAPHQL  {}------ {} seconds ------\n".format(inventory_clusters_serviceinstance, cost))
    test_results["FindServiceInstances"] = cost
    args.log.info("\n\n")


    args.log.info("3rd query")
    for interval in time_interval:
        inventory_table = 'query clusterInventoryTable($startTime: String, $endTime: String) { root { inventory { clusters { name queryClusterTable(startTime: $startTime, endTime: $endTime, noMetrics: true) { data __typename } __typename } __typename } __typename}}'
        variables = {
            "startTime": '%s' % (time.time() - interval * 60),
            "endTime": '%s' % (time.time())
        }	
        cost = 0
        for x in range(0, loop):
            cost += execute_query(graph_cli, inventory_table, variables=variables, log=args.log)
            args.log.info("loop {} x {} cost {}".format(loop, x, cost))
        cost = cost/loop
        args.log.info("\nGRAPHQL  {}-- the past {} mins------ {} seconds ------\n".format(inventory_table, interval, cost))
        test_results["clusterInventoryTable::"+ str(interval) + "mins"] = cost
    args.log.info("\n\n")
    
    args.log.info("4th query")
    for interval in time_interval:
        #inventory_cluster_service_metrics = 'query FindServiceMetrics($cluster: String, $startTime: String, $endTime: String) {root {inventory {clusters(name: $cluster) { name queryServiceTable(startTime: $startTime,endTime: $endTime) {data}}}}}'
        inventory_cluster_service_metrics = 'query inventoryServiceTable($startTime: String, $endTime: String, $showGateways: String, $noMetrics: String) {root {inventory { queryServiceTable(startTime: $startTime, endTime: $endTime, showGateways: true, noMetrics: true) { data}}}}'
        variables = {
            "startTime": '%s' % (time.time() - interval * 60),
            "endTime": '%s' % (time.time()),
            # "cluster": client_cluster
        }
        cost = 0
        for x in range(0, loop):
            cost += execute_query(graph_cli, inventory_cluster_service_metrics, variables=variables, log=args.log)
            args.log.info("loop {} x {} cost {}".format(loop, x, cost))
        cost = cost/loop
        args.log.info("\nGRAPHQL  {}-- the past {} mins ------ {} seconds ------\n".format(inventory_cluster_service_metrics, interval, cost))
        test_results['FindServiceMetrics::inventory::'+ str(interval) + "mins"] = cost
    args.log.info("\n\n")

    args.log.info("5th query")
    for interval in time_interval:
        for service_metric_types in ServiceMetricTypes:
            inventory_cluster_domain = '''query FindServiceMetrics($metric: ServiceMetricTypeEnum $cluster: String $domain: String $service: String $startTime: String $endTime: String) 
        {root {inventory {clusters(name: $cluster) {domains(name: $domain) {name services(name: $service) {name queryServiceTS(svcMetric: $metric, startTime: $startTime, endTime: $endTime, timeInterval: "10s") {data} serviceDeployments { serviceInstances { nodeName }}}}
        queryServiceTS(svcMetric: $metric, startTime: $startTime, endTime: $endTime, timeInterval: "10s") {data}}}}}'''
            variables = {
                "metric": service_metric_types,
                "startTime": '%s' % (time.time() - interval * 60),
                "endTime": '%s' % (time.time()),
                "cluster": client_cluster,
                "domain": "gns-2ns-sc.local",
                "service": "fortioserver"
            }
            cost = 0
            for x in range(0, loop):
                cost += execute_query(graph_cli, inventory_cluster_domain, variables=variables, log=args.log)
                args.log.info("loop {} x {} cost {}".format(loop, x, cost))
            cost = cost/loop
            args.log.info("\nGRAPHQL  {}---metric_type {}-- the past {} mins ------ {} seconds ------\n".format(inventory_cluster_domain, service_metric_types, interval, cost))
            test_results["FindServiceMetrics::"+ service_metric_types + '::'+ str(interval) + "mins"] = cost
    args.log.info("\n\n")



    args.log.info("6th query")
    for interval in time_interval:
        inventory_service_topology = '''query FindServiceTopology($cluster: String $domain: String $service: String $startTime: String $endTime: String) {
    root {inventory {clusters(name: $cluster) {name domains(name: $domain) {name services(name: $service) {name queryServiceTopology(startTime: $startTime, endTime: $endTime) {data}}}}}}}'''
        variables = {
            "startTime": '%s' % (time.time() - interval * 60),
            "endTime": '%s' % (time.time()),
            "cluster": "dd-cl3-dev-st",
            "domain": "gns-2ns-sc.local",
            "service": "fortioserver"
        }
        cost = 0
        for x in range(0, loop):
            cost += execute_query(graph_cli, inventory_service_topology, variables=variables, log=args.log)
            args.log.info("loop {} x {} cost {}".format(loop, x, cost))
        cost = cost/loop
        args.log.info("\nGRAPHQL  {}-- the past {} mins------ {} seconds ------\n".format(inventory_service_topology, interval, cost))
        test_results['FindServiceTopology::'+ str(interval) + "mins"] = cost
    args.log.info("\n\n")


    args.log.info("7th query")
    for interval in time_interval:
        for node_metric_type in NodeMetricTypes :
            inventory_cluster_node_query = '''query FindClusterNodesMetrics($metric: NodeMetricTypeEnum $cluster: String $startTime: String $endTime: String)
            {root {inventory {clusters(name: $cluster) {nodes {name queryNodeTS(nodeMetric: $metric, startTime: $startTime, endTime: $endTime, timeInterval: "10s") {data}}}}}}'''
            variables = {
                "metric": node_metric_type,
                "startTime": '%s' % (time.time() - interval * 60),
                "endTime": '%s' % (time.time()),
                "cluster": client_cluster
            }
            cost = 0
            for x in range(0, loop):
                cost += execute_query(graph_cli, inventory_cluster_node_query, variables=variables, log=args.log)
                args.log.info("loop {} x {} cost {}".format(loop, x, cost))
            cost = cost/loop
            args.log.info("\nGRAPHQL  interval{}/node_metric_type{}/{}/{}------ {} seconds ------\n".format(interval, node_metric_type, inventory_cluster_node_query, variables, cost))
            test_results['FindClusterNodesMetrics::'+ node_metric_type + "::" + str(interval) + "mins"] = cost
    args.log.info("\n\n")



    args.log.info("8th query")
    for interval in time_interval:
        inventory_cluster_nodetable = 'query GetNodeTable($cluster: String, $startTime: String, $endTime: String) {root {inventory {clusters(name: $cluster) {queryNodeTable (startTime: $startTime, endTime: $endTime) {data}}}}}'
        variables = {
            "startTime": '%s' % (time.time() - interval * 60),
            "endTime": '%s' % (time.time()),
            "cluster": client_cluster
        }
        cost = 0
        for x in range(0, loop):
            cost += execute_query(graph_cli, inventory_cluster_nodetable, variables=variables, log=args.log)
            args.log.info("loop {} x {} cost {}".format(loop, x, cost))
        cost = cost/loop
        args.log.info("\nGRAPHQL  {}--the past {} mins ------ cost {} seconds ------\n".format(inventory_cluster_nodetable, interval, cost))
        test_results['GetNodeTable::'+ str(interval) + "mins"] = cost
    args.log.info("\n\n")



    args.log.info("10th query")
    for interval in time_interval:
        inventory_cluster_count = 'query GetClusterInventory {root {inventory {queryClusterInventoryCount(startTime: $startTime, endTime: $endTime, timeInterval: "10s") {data}}}}'
        variables = {
                    "startTime": '%s' % (time.time() - interval * 60),
                    "endTime": '%s' % (time.time())
                    }
        cost = 0
        for x in range(0, loop):
            cost += execute_query(graph_cli, inventory_cluster_nodetable, variables=variables, log=args.log)
            args.log.info("loop {} x {} cost {}".format(loop, x, cost))
        cost = cost/loop
        args.log.info("\nGRAPHQL  {} --the past {} mins ------ cost {} seconds ------\n".format(inventory_cluster_nodetable, interval, cost))
        test_results['GetClusterInventory::'+ str(interval) + "mins"] = cost
    args.log.info("\n\n")



    args.log.info("11th query")
    inventory_cluster_connection = 'query GetClusterConnection($cluster: String) {root {inventory {clusters(name: $cluster) {connected}}}}'
    cost = 0
    for x in range(0, loop):
        cost += execute_query(graph_cli, inventory_cluster_nodetable, log=args.log)
        args.log.info("loop {} x {} cost {}".format(loop, x, cost))
    cost = cost/loop
    args.log.info("\nGRAPHQL  {}------ {} seconds ------\n".format(inventory_cluster_nodetable, cost))
    test_results["GetClusterConnection"] = cost
    args.log.info("\n\n")



    args.log.info("12nd query")
    inventory_get_cluster = 'query GetClusterUUID($cluster: String) {root {inventory {clusters(name: $cluster) {uuid}}}}'
    variables = {"cluster": client_cluster}
    cost = 0
    for x in range(0, loop):
        cost += execute_query(graph_cli, inventory_get_cluster, variables=variables, log=args.log)
        args.log.info("loop {} x {} cost {}".format(loop, x, cost))
    cost = cost/loop
    args.log.info("\nGRAPHQL  {}------ {} seconds ------\n".format(inventory_get_cluster, cost))
    test_results["GetClusterUUID"] = cost
    args.log.info("\n\n")


    args.log.info("13rd query")
    for interval in time_interval:
        inventory_servicets_p50_latency = 'query {root{inventory{queryServiceTS(svcMetric: p50Latency, startTime: $startTime", endTime: $endTime, timeInterval:"1m") { data code } } } } '
        variables = {
                    "startTime": '%s' % (time.time() - interval * 60),
                    "endTime": '%s' % (time.time())
                    }
        cost = 0
        for x in range(0, loop):
            cost += execute_query(graph_cli, inventory_cluster_connection, variables=variables, log=args.log)
            args.log.info("loop {} x {} cost {}".format(loop, x, cost))
        cost = cost/loop
        args.log.info("\nGRAPHQL  {} -- the past {} mins ------ {} seconds ------\n".format(inventory_cluster_connection, interval, cost))
        test_results["queryServiceTS"] = cost
    args.log.info("\n\n")


    args.log.info("14th query")
    gns_config =  '''query ListGlobalNamespaces {root { config {globalNamespace {gns {name}}}}}'''
    cost = 0
    for x in range(0, loop):
        cost += execute_query(graph_cli, gns_config, log=args.log)
        args.log.info("loop {} x {} cost {}".format(loop, x, cost))
    cost = cost/loop
    args.log.info("\n\GRAPHQL  {}------ {} seconds ------\n".format(gns_config, cost))
    test_results["ListGlobalNamespaces"] = cost
    args.log.info("\n\n")     


    args.log.info("15th query")
    gns_details_query =  '''query GetGlobalNamespace($name: String) {root {config {globalNamespace {gns(name: $name) {
   name description color domain caType  ca version matchingConditions }}}}}'''
    variables = {"name": "f93krq"}
    cost = 0
    for x in range(0, loop):
        cost += execute_query(graph_cli, gns_details_query, variables=variables, log=args.log)
        args.log.info("loop {} x {} cost {}".format(loop, x, cost))
    cost = cost/loop
    args.log.info("\nGRAPHQL  {}------ {} seconds ------\n".format(gns_details_query, cost)) 
    test_results["GetGlobalNamespace"] = cost
    args.log.info("\n\n")

    args.log.info("16th query")
    for interval in time_interval:
        gns_service_metrics = 'query FindServiceMetrics($gnsName: String, $startTime: String, $endTime: String) {root {config {globalNamespace {gns(name: $gnsName) {queryServiceInstanceTable(startTime: $startTime, endTime: $endTime) {data}}}}}}'
        variables = {
            "startTime": '%s' % (time.time() - interval * 60),
            "endTime": '%s' % (time.time()),
            "gnsName": 'f93krq'
        }
        cost = 0
        for x in range(0, loop):
            cost += execute_query(graph_cli, gns_service_metrics, variables=variables, log=args.log)
            args.log.info("loop {} x {} cost {}".format(loop, x, cost))
        cost = cost/loop
        test_results["FindServiceMetrics::globalNamespace::" + str(interval) + "mins"] = cost
        args.log.info("\nGRAPHQL  {}-- the past {} mins ------ {} seconds ------\n".format(gns_service_metrics, interval, cost))
    args.log.info("\n\n")

    try:
        fd = os.open("graphql_measurement.json", os.O_RDWR|os.O_CREAT)
        out = os.fdopen(fd, "wt")
        print("graphql measurement results {}".format(json.dumps(test_results)))
        out.write(json.dumps(test_results) + "\n")
        out.close()
    except Exception:
        raise "failed dumping data into graphql_measurement.json"
