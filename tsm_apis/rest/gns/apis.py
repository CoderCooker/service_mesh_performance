# Copyright 2020 VMware, Inc.  All rights reserved. -- VMware Confidential
# Description: config module for service mesh performance
# Group-pods-st: optional
# Disabled: false
# Timeout: 24000

from library.utils import *
from library.constants import *
from library.kubenertes_utils import *

import traceback
from library.utils import CSP, request
from library.gns_utils import GNS
from tsm_apis.graphql.queries import GraphQLClient, execute_query

import json

def psv_apis(client_cluster, gns, log=None):
    name = ''.join(random.choices(string.ascii_lowercase + string.digits, k = 6))
    try:
    
       create_namespace(client_cluster, name, log)
       gns_config_dict = dict()
       gns_config_dict[client_cluster] = [name]
       gns.save(gns_config_dict, 'acme.com', name)

       resp = gns.create_external_account(name)
       external_accounts_id = resp['id']
       
       resp = gns.create_external_dns(name, external_accounts_id)
       ext_dns_id = resp['id']
       
       sub_dom = "tsm-perf-create-http-pub-svc-{}".format(name)
       psv_config = gns.config_psv(ext_dns_id, name, sub_dom)

       fqdn= "tsm-perf-create-http-pub-svc-{}.servicemesh.biz".format(name)
       resp = gns.create_psv(name, fqdn, psv_config)
       
       gns.delete_pvs(name, fqdn)
    except Exception as e:
        traceback.format_exc()
        raise     

def gns_2clusters_5services(clusters, gns, graph_cli, log=None, test_name_space=None, test_gns_domain=None, cluster_type="EKS"):

    # create_namespaces
    random_num = ''.join(random.choices(string.ascii_lowercase + string.digits, k = 6))
    test_name_space = "{}-{}".format(test_name_space, random_num)
    for cluster in clusters:
        assert prepare_cluster(cluster, log=log, cluster_type=cluster_type) == 0, "Failed connecting {}".format(cluster)
        create_namespace(cluster, test_name_space, log=log)

    # deploy_services, deploy load generator
    if cluster_type=='EKS':
        cls1_context = "{}/{}".format(AWS_EKS_DESC, clusters[0])
        for cls_1_yaml in GNS_VERIFICATION_CLS1_YAMLS:
            deploy_service = "kubectl --context {} -n {} apply -f {}".format(cls1_context, test_name_space, cls_1_yaml)
            log.info("deploying to cls1 {}".format(deploy_service))
            rt, out, err = run_local_sh_cmd(deploy_service)
            log.info("deploying yaml {} on {} rt {} out {} err {}.".format(cls_1_yaml, clusters[0], rt, out, err))
            assert rt == 0, "Failed deploying {} yaml on cluster 1 {}, err {}".format(cls_1_yaml, clusters[0], err)
    elif cluster_type.upper()=='KIND':
        raise "Currently, do not use kind testing this yet."

    if cluster_type=='EKS':
        cls2_context = "{}/{}".format(AWS_EKS_DESC, clusters[1])
        for cls_2_yaml in GNS_VERIFICATION_CLS2_YAMLS:
            deploy_service = "kubectl --context {} -n {} apply -f {}".format(cls2_context, test_name_space, cls_2_yaml)
            log.info("deploying to cls2 {}".format(deploy_service))
            rt, out, err = run_local_sh_cmd(deploy_service)
            log.info("deploying yaml {} on {} rt {} out {} err {}.".format(cls_2_yaml, clusters[1], rt, out, err))
            assert rt == 0, "Failed deploying {} yaml on cluster 2 {}, err {}".format(cls_2_yaml, clusters[1], err)
    elif cluster_type.upper()=='KIND':
        raise "Currently, do not use kind testing this yet."

    # create GNS generate load from shopping to services users/cart/catalog/order
    gns_config_dict = dict()
    gns_config_dict[clusters[1]] = [test_name_space]
    gns_config_dict[clusters[0]] = [test_name_space]

    start = time.time()
    gns_name = ''.join(random.choices(string.ascii_lowercase + string.digits, k = 6))
    try:
        gns_obj = gns.save(gns_config_dict, test_gns_domain, gns_name=gns_name)
    except Exception as e:
        raise
    check_gns_availability(graph_cli, gns_name=gns_name, log=log, start=start)

    # cleanup
    log.info("clean setup. deleting gns, namespaces.")
    gns.delete(gns_name)
    del_namespace(clusters[0], cls1_context, test_name_space, log=log, kubeconfig=None)
    del_namespace(clusters[1], cls2_context, test_name_space, log=log, kubeconfig=None)

# veriy services are available and traffic is among services
def check_gns_availability(graph_cli, gns_name=None, log=None, start=None):
    while True:
        try:
            gns_query = "query globalNamespaceTopology($name: String, $startTime: String, $endTime: String, $noMetrics: Boolean, $withServiceVersions: Boolean!) {\n  root {\n    config {\n      globalNamespace {\n        gns(name: $name) {\n          name\n          queryServiceTopology: queryServiceTopology(\n            startTime: $startTime\n            endTime: $endTime\n          ) {\n            data\n            __typename\n          }\n          queryServiceTable: queryServiceTable(\n            startTime: $startTime\n            endTime: $endTime\n            noMetrics: $noMetrics\n            ShowGateways: true\n          ) {\n            data\n            __typename\n          }\n          queryServiceVersionTable: queryServiceVersionTable(\n            startTime: $startTime\n            endTime: $endTime\n            noMetrics: $noMetrics\n            ShowGateways: true\n          ) @include(if: $withServiceVersions) {\n            data\n            __typename\n          }\n          queryClusterTable(\n            startTime: $startTime\n            endTime: $endTime\n            noMetrics: $noMetrics\n          ) {\n            data\n            __typename\n          }\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}\n"
            variables = {
            "name": gns_name,
            "startTime": "now() - 1h",
            "endTime": "now()",
            "noMetrics": False,
            "withServiceVersions": True
            }
            resp = execute_query(graph_cli, gns_query, variables=variables, log=log, return_content=True)
            # log.info("\n gns query --->{} resp --->{} \n".format(gns_query, resp))
            json_obj = json.loads(resp)
           
            if json_obj["data"] is not None:
                if json_obj["data"]["root"] is not None:
                    if json_obj["data"]["root"]["config"] is not None:
                        if json_obj["data"]["root"]["config"]["globalNamespace"] is not None:
                            if json_obj["data"]["root"]["config"]["globalNamespace"]["gns"] is not None:
                                gns_resp = json_obj["data"]["root"]["config"]["globalNamespace"]["gns"]
                                for gns_item in gns_resp:
                                    # log.info("the gns name {}".format(gns_item["name"]))
                                    if gns_name == gns_item["name"]:
                                        if "queryServiceTopology" in gns_item:
                                            queryServiceTopology_data = gns_item["queryServiceTopology"]["data"]
                                            # log.info("interesting {} queryServiceTopology_data {} size {} \n".format(gns_item["queryServiceTopology"], queryServiceTopology_data, len(queryServiceTopology_data)))
                                        if "queryServiceTable" in gns_item:
                                            queryServiceTable_data = gns_item["queryServiceTable"]["data"]
                                            # log.info(" queryServiceTable_data {} size {}\n".format(queryServiceTable_data, len(queryServiceTable_data)))
                                        if "queryServiceVersionTable" in gns_item:
                                            queryServiceVersionTable_data = gns_item["queryServiceVersionTable"]["data"]
                                            # log.info(" queryServiceVersionTable_data {} size {} \n".format(queryServiceVersionTable_data,
                                            # len(queryServiceVersionTable_data)))
                                        if "queryClusterTable" in gns_item:
                                            queryClusterTable_data = gns_item["queryClusterTable"]["data"]
                                            # log.info(" queryClusterTable_data {} size {} \n".format(queryClusterTable_data, len(queryClusterTable_data)))
                                        if (queryServiceTopology_data is not None and len(queryServiceTopology_data) > 10 ) and\
                                            (queryServiceTable_data is not None and len(queryServiceTable_data) > 10) and\
                                            (queryServiceVersionTable_data is not None and len(queryServiceVersionTable_data) > 10) and\
                                            (queryClusterTable_data is not None and len(queryClusterTable_data) > 10):
                                            # log.info("Traffic is observed from service to service. GNS works as expected.")
                                            end = time.time()
                                            gns_cost = end - start
                                            log.info("GNS Generation Corss clusters with five services cost {}".format(gns_cost))
                                            return
                                        log.info("service traffic is not available yet. sleep and retry.")
                                        time.sleep(10)
        except Exception as e:
            raise

def gns_apis(client_cluster, gns, log=None):
    try:
        namespace = ''.join(random.choices(string.ascii_lowercase + string.digits, k = 5))
        namespace = "tsm-perf-resthttp-ns-{}".format(namespace)
        create_namespace(client_cluster, namespace, log=log)
        
        gns_config_dict = dict()
        gns_config_dict[client_cluster] = [namespace]
        gns_name = ''.join(random.choices(string.ascii_lowercase + string.digits, k = 6))
        gns_obj = gns.save(gns_config_dict, '{}.local'.format(namespace), gns_name=gns_name)
        gns.get(gns_name)
        gns.list_gns()
        gns.delete(gns_name)
    except Exception as e:
        traceback.format_exc()
        raise

def Run(args):
    args.log.info("start testing %s"%(args.shortName))
    csp_token = os.getenv("CSP_TOKEN") if os.getenv("CSP_TOKEN") else args.opts.cspToken
    
    #client_cluster = os.getenv("CLUSTER") if os.getenv("CLUSTER") else args.opts.singleCluster
    clusters = os.getenv("CLUSTERS") if os.getenv("CLUSTERS") else args.opts.clusterLists
    cluster_type = os.getenv("CLUSTER_TYPE") if os.getenv("CLUSTER_TYPE") else args.opts.clusterType
    #assert prepare_cluster(client_cluster, log=args.log, cluster_type=cluster_type) == 0, "Failed connecting {}".format(client_cluster)

    gns = GNS(csp_token, log=args.log)
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

    gns_domain = "cc-2ns-bookinfo.local"
    gns_test_ns = "acme"
    clusters = clusters.split(",")
    gns_2clusters_5services(clusters, gns, graph_cli, log=args.log, test_name_space=gns_test_ns, test_gns_domain=gns_domain)
    # GET /v1alpha1/global-namespaces/{id}/capabilities/{capability}
    # GET /v1alpha1/global-namespaces/{id}/capabilities
    # GET /v1alpha1/global-namespaces/{id}/members
    # PUT /v1alpha1/global-namespaces/{id}/routing-policy/{routingPolicyId}
    # PUT /v1alpha1/global-namespaces/{id}
    # GET /v1alpha1/global-namespaces/{id}
    # DELETE /v1alpha1/global-namespaces/{id}
    # POST /v1alpha1/global-namespaces
    # GET /v1alpha1/global-namespaces
    #gns_name = "dfgphk"
    #check_gns_availability(graph_cli, gns_name=gns_name, log=args.log)
