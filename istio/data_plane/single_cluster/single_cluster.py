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

def config_fortio(cluster, log=None):
    try:
        create_namespace(cluster, FORTIO_CLIENT_NAMESPACE, log=log)
        context = "{}/{}".format(AWS_EKS_DESC, cluster)
        
        config_fortio_client = "kubectl --context {} -n {} apply -f {}".format(context, FORTIO_CLIENT_NAMESPACE, GNS_SC_CLIENT_YAML)
        log.info("configuring fortio client on {}".format(cluster))
        rt, out, err = run_local_sh_cmd(config_fortio_client)
        assert rt == 0, "Failed configuring fortio client on {}, err {}".format(cluster, err)
        wait_for_pods_ready(cluster_name=cluster, context=context, namespace=FORTIO_CLIENT_NAMESPACE, num_pods=1)

        create_namespace(cluster, FORTIO_SERVER_NAMESPACE, log=log)
        
        config_fortio_server = "kubectl --context {} -n {} apply -f {}".format(context, FORTIO_SERVER_NAMESPACE, GNS_SC_SERVER_YAML)
        log.info("configuring fortio server on {}".format(cluster))
        rt, out, err = run_local_sh_cmd(config_fortio_server)
        assert rt == 0, "Failed configuring fortio server on {}, err {}".format(cluster, err)
        wait_for_pods_ready(cluster_name=cluster, context=context, namespace=FORTIO_SERVER_NAMESPACE, num_pods=1)
        return 0
    except Exception as e:
        traceback.format_exc()
        raise

def config_gns(csp_token, cluster, log=None):
    try:
        gns = GNS(csp_token, log=log)
        gns.save({cluster: [FORTIO_CLIENT_NAMESPACE, FORTIO_SERVER_NAMESPACE]}, GNS_SC_DOMAIN)
        time.sleep(10)
        return 0
    except Exception as e:
        traceback.format_exc()
        raise


def process_results(json_res, csv_res, conn_list, qps_list, log=None):
    try:
        log.info("generating latency graph.")
        file_path = "/var/lib/jenkins/jobs/%s/builds/%s" % (os.getenv("JOB_NAME"), os.getenv("BUILD_NUMBER"))
        graph_type = "latency-p999"
        argv = ["--graph_type={}".format(graph_type), "--x_axis=conn", "--telemetry_modes=v2-stats-nullvm_both", "--query_list={}".format(conn_list), "--query_str=ActualQPS==1000", "--csv_filepath={}".format(csv_res), "--graph_title={}/{}.png".format(file_path, graph_type)]
        processed_args = get_parser().parse_args(argv)
        log.info("processed parameters {}".format(processed_args))
        plotter(processed_args)

        log.info("generating cpu/memory/network graph.")
        graph_type = "cpu-istio-ingressgateway"
        argv = ["--graph_type={}".format(graph_type), "--x_axis=qps", "--telemetry_modes=v2-stats-nullvm_both", "--query_list={}".format(qps_list), "--query_str=NumThreads==16", "--csv_filepath={}".format(csv_res), "--graph_title={}/{}.png".format(file_path, graph_type)]
        processed_args = get_parser().parse_args(argv)
        log.info("processed parameters {}".format(processed_args))
        plotter(processed_args)
        return 0
    except Exception as e:
        traceback.format_exc()
        raise

def Run(args):
    args.log.info("start testing %s"%(args.shortName))
    client_cluster = args.opts.singleCluster
    csp_token = args.opts.cspToken
    protocolMode = args.opts.protocolMode
    assert client_cluster and len(client_cluster) > 0, "please sepcify cluster to be tested."
    assert csp_token and len(csp_token) > 0, "please specify csp fresh token."
    assert protocolMode and len(protocolMode) > 0, "please specify tests prototype."

    assert prepare_cluster(client_cluster, log=args.log) == 0, "Failed connecting {}".format(client_cluster)
    assert config_fortio(client_cluster, log=args.log) == 0, "Failed configuring fortio on {}".format(client_cluster)
    assert config_gns(csp_token, client_cluster, log=args.log) == 0, "Failed configuring gns on {}".format(client_cluster)

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
            load_tests_cmd(client_cluster, pod_name, GNS_SC_DOMAIN, uid, conn=conns, qps=1000, duration=240, proto=protocolMode, log=args.log)

        args.log.info("Collecting cpu/memory/network data.")
        for qps in qps_list:
            load_tests_cmd(client_cluster, pod_name, GNS_SC_DOMAIN, uid, conn=16, qps=qps, duration=240, proto=protocolMode, log=args.log)
    
    json_res, csv_res = generate_tests_results(client_cluster, log=args.log)
    args.log.info("Generated test json results {} csv result {}".format(json_res, csv_res))

    # args.log.info("Visualize tests results")
    # assert process_results(json_res, csv_res, '32,64', '400, 800', log=args.log) == 0, "Failed visualizing tests results {}".format(csv_res)

    scale_pod(client_cluster, FORTIO_CLIENT_NAMESPACE, FORTIO_CLIENT_DEPLOYMENT, 1, log=args.log)
    
