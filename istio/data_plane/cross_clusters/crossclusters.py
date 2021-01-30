# Copyright 2020 VMware, Inc.  All rights reserved. -- VMware Confidential
# Description: config module for service mesh performance
# Group-pods-st: optional
# Disabled: False
# Timeout: 24000

import sys
from os.path import dirname, abspath
sys.path.insert(0, dirname(dirname(abspath(__file__))))
sys.path.append(dirname(abspath(__file__)))
from library.utils import *
from library.constants import *
from library.kubenertes_utils import *
from library.fortio import load_tests_cmd, generate_tests_results
import traceback
from time import sleep
from library.gns_utils import GNS
from prometheus.setup import *


def config_fortio(client_cluster, cluster_server, log=None):
    try:
        create_namespace(client_cluster, FORTIO_CLIENT_NAMESPACE, log=log)
        context = "{}/{}".format(AWS_EKS_DESC, client_cluster)
        config_fortio_client = "kubectl --context {} -n {} apply -f {}".format(context, FORTIO_CLIENT_NAMESPACE, GNS_CC_CLIENT_YAML)
        log.info("configuring fortio client on {}".format(client_cluster))
        rt, out, err = run_local_sh_cmd(config_fortio_client)
        assert rt == 0, "Failed configuring fortio client on {}, err {}".format(client_cluster, err)
        wait_for_pods_ready(cluster_name=client_cluster, context=context, namespace=FORTIO_CLIENT_NAMESPACE, num_pods=1)

        create_namespace(cluster_server, FORTIO_SERVER_NAMESPACE, log=log)
        context = "{}/{}".format(AWS_EKS_DESC, cluster_server)
        config_fortio_server = "kubectl --context {} -n {} apply -f {}".format(context, FORTIO_SERVER_NAMESPACE, GNS_CC_SERVER_YAML)
        log.info("configuring fortio server on {}".format(cluster_server))
        rt, out, err = run_local_sh_cmd(config_fortio_server)
        assert rt == 0, "Failed configuring fortio server on {}, err {}".format(cluster_server, err)
        wait_for_pods_ready(cluster_name=cluster_server, context=context, namespace=FORTIO_SERVER_NAMESPACE, num_pods=1)
        return 0
    except Exception as e:
        traceback.format_exc()
        raise
    return 0

def config_gns(csp_token, client_cluster, server_cluster, log=None):
    try:
        gns = GNS(csp_token, log=log)
        gns.save({client_cluster: [FORTIO_CLIENT_NAMESPACE], server_cluster: [FORTIO_SERVER_NAMESPACE]}, GNS_CC_DOMAIN)
        return 0
    except Exception as e:
        traceback.format_exc()
        raise

def Run(args):
    args.log.info("start testing %s"%(args.shortName))
    client_cluster = args.opts.clientCluster
    server_cluster = args.opts.serverCluster
    csp_token = args.opts.cspToken
    protocolMode = args.opts.protocolMode

    assert prepare_cluster(client_cluster, log=args.log) == 0, "Failed connecting fortio client {}".format(client_cluster)
    assert prepare_cluster(server_cluster, log=args.log) == 0, "Failed connecting fortio server {}".format(client_cluster)
    assert config_fortio(client_cluster, server_cluster, log=args.log) == 0, "Failed configuring fortio on {} and {}".format(client_cluster, server_cluster)
    assert config_gns(csp_token, client_cluster, server_cluster, log=args.log) == 0, "Failed configure GNS on {}".format(client_cluster)

    pods_nums = [10, 50, 100, 250]
    uid = generate_randoms()
    connections = [1, 2, 4, 8, 16, 32, 64]
    qps_list = [100, 200, 400, 800]
    for pod_num in pods_nums:
        args.log.info("Scaling Pods to {}.".format(pod_num))
        scale_pod(client_cluster, FORTIO_CLIENT_NAMESPACE, FORTIO_CLIENT_DEPLOYMENT, pod_num, log=args.log)
        pod_name = get_pod(client_cluster, FORTIO_CLIENT_NAMESPACE, "fortioclient", log=args.log)
        
        args.log.info("Collecting latency data.")
        for conns in connections:
            load_tests_cmd(client_cluster, pod_name, GNS_CC_DOMAIN, uid, conn=conns, qps=1000, duration=100, proto=protocolMode, log=args.log)

        args.log.info("Collecting cpu/memory/network data.")
        for qps in qps_list:
            load_tests_cmd(client_cluster, pod_name, GNS_CC_DOMAIN, uid, conn=16, qps=qps, duration=100, proto=protocolMode, log=args.log)

    args.log.info("Generating Tests Results.")
    json_res, csv_res = generate_tests_results(client_cluster, log=args.log) == 0, "failed generating tests results."

    scale_pod(client_cluster, FORTIO_CLIENT_NAMESPACE, FORTIO_CLIENT_DEPLOYMENT, 1, log=args.log)