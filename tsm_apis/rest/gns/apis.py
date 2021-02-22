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

def gns_2clusters_5services(clusters, gns, graph_cli, log=args.log, ns="cc-2ns-bookinfo", cluster_type='EKS'):

    # create_namespaces
    for cluster in clusters:
        assert prepare_cluster(cluster, log=log, cluster_type=cluster_type) == 0, "Failed connecting {}".format(cluster)
        create_namespace(cluster, ns, log=log)

    # deploy_services, deploy load generator
    if cluster_type=='EKS':
        cls1_context = "{}/{}".format(AWS_EKS_DESC, clusters[0])
        for cls_1_yaml in GNS_VERIFICATION_CLS1_YAMLS:
            deploy_service = "kubectl --context {} apply -f {}".format(cls1_context, cls_1_yaml)
            rt, out, err = run_local_sh_cmd(deploy_service)
            log.info("deploying yaml {} on {} rt {} out {} err {}.".format(cls_1_yaml, clusters[0], rt, out, err))
            assert rt == 0, "Failed deploying {} yaml on cluster 1 {}, err {}".format(cls_1_yaml, clusters[0], err)
    elif cluster_type.upper()=='KIND':
        raise "Currently, do not use kind testing this yet."

    if cluster_type=='EKS':
        cls2_context = "{}/{}".format(AWS_EKS_DESC, clusters[1])
        for cls_2_yaml in GNS_VERIFICATION_CLS2_YAMLS:
            deploy_service = "kubectl --context {} apply -f {}".format(cls2_context, cls_2_yaml)
            rt, out, err = run_local_sh_cmd(deploy_service)
            log.info("deploying yaml {} on {} rt {} out {} err {}.".format(cls_2_yaml, clusters[0], rt, out, err))
            assert rt == 0, "Failed deploying {} yaml on cluster 2 {}, err {}".format(cls_2_yaml, clusters[0], err)
    elif cluster_type.upper()=='KIND':
        raise "Currently, do not use kind testing this yet."

    # create GNS generate load from shopping to services users/cart/catalog/order
    start = time.time()
    gns_config_dict = dict()
    gns_config_dict[clusters[1]] = [ns]
    gns_config_dict[clusters[0]] = [ns]

    gns_name = ''.join(random.choices(string.ascii_lowercase + string.digits, k = 6))
    gns_obj = gns.save(gns_config_dict, '{}.local'.format(ns), gns_name=gns_name)

    # veriy services are available and traffic is among services
    # kubectl --context arn:aws:eks:us-west-2:284299419820:cluster/dd-cl3-dev-st -n acme exec -it shopping-79b67f7ccb-r7kqx -- wget http://users.cc-2ns-bookinfo.com:8081/users
    while True:
        try:
            gns_query = "query globalNamespaceTopology($name: String, $startTime: String, $endTime: String, $noMetrics: Boolean, $withServiceVersions: Boolean!) {\n  root {\n    config {\n      globalNamespace {\n        gns(name: $name) {\n          name\n          queryServiceTopology: queryServiceTopology(\n            startTime: $startTime\n            endTime: $endTime\n          ) {\n            data\n            __typename\n          }\n          queryServiceTable: queryServiceTable(\n            startTime: $startTime\n            endTime: $endTime\n            noMetrics: $noMetrics\n            ShowGateways: true\n          ) {\n            data\n            __typename\n          }\n          queryServiceVersionTable: queryServiceVersionTable(\n            startTime: $startTime\n            endTime: $endTime\n            noMetrics: $noMetrics\n            ShowGateways: true\n          ) @include(if: $withServiceVersions) {\n            data\n            __typename\n          }\n          queryClusterTable(\n            startTime: $startTime\n            endTime: $endTime\n            noMetrics: $noMetrics\n          ) {\n            data\n            __typename\n          }\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}\n"
            variables = {
            "name": gns_name,
            "startTime": "now() - 1h",
            "endTime": "now()",
            "noMetrics": false,
            "withServiceVersions": true
            }
            resp = execute_query(graph_cli, gns_query, variables=variables, log=args.log, return_content=True).json()
            log.info("\n gns query {} resp {} \n".format(gns_query, resp))
            gns_resp = resp["data"]["root"]["config"]["globalNamespace"]["gns"]
            if gns_resp:
                for gns_item in gns_resp:
                    if gns_name == gns_item["name"]:
                        queryServiceTopology_data = gns_item["queryServiceTopology"]
                        queryServiceTable_data = gns_item["queryServiceTable"]
                        queryServiceVersionTable_data = gns_item["queryServiceVersionTable"]
                        queryClusterTable_data = gns_item["queryClusterTable"]
                        if queryServiceTopology_data and queryServiceTable_data and queryServiceVersionTable_data and queryClusterTable_data:
                            log.info("Traffic is generated from service to service. GNS works as expected.")
                            break
            log.info("No traffic from service to service yet. sleep and retry")
            time.sleep(10)
        except Exception as e:
            raise

    end = time.time()
    gns_cost = end - start
    log.info("GNS Generation Corss clusters with five services cost {}".format(cost))
    # cleanup

    # delete gns
    gns.delete(gns_name)
    # delete namespaces
    delete_service = "kubectl --context {} delete -f {}".format(cls1_context, cls_1_yaml)
    del_namespace(clusters[0], cls1_context, ns, log=log, kubeconfig=None)
    del_namespace(clusters[1], cls2_context, ns, log=log, kubeconfig=None)


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
    gns = GNS(csp_token, log=args.log)
    client_cluster = os.getenv("CLUSTER") if os.getenv("CLUSTER") else args.opts.singleCluster
    cluster_type = os.getenv("CLUSTER_TYPE") if os.getenv("CLUSTER_TYPE") else args.opts.clusterType
    assert prepare_cluster(client_cluster, log=args.log, cluster_type=cluster_type) == 0, "Failed connecting {}".format(client_cluster)

    gns_apis(client_cluster, gns, log=args.log)

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

    gns_2clusters_5services(clusters, gns, graph_cli, log=args.log, ns="cc-2ns-bookinfo")
    #psv_apis(client_cluster, gns, log=args.log)
