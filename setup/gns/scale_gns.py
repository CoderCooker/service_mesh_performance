# Copyright 2020 VMware, Inc.  All rights reserved. -- VMware Confidential
# Description: config module for service mesh performance
# Group-pods-st: optional
# Disabled: false
# Timeout: 24000

from tsm_apis.rest.onoffboard.boardapis import *
from library.kubenertes_utils import *
from library.gns_utils import GNS

def config_gns(csp_token, gns_dict=None, domain_name=None, log=None):
    try:
        gns = GNS(csp_token, log=log)
        log.info("gns dictionary {}")
        gns.save(gns_dict, domain_name)
        return 0
    except Exception as e:
        traceback.format_exc()
        raise

def deploy_config(cluster, namespace, i, log=args.log):
    log.info('skip deploy the app cluster i manifest into namespace')
    return

def Run(args):
    args.log.info("start testing %s"%(args.shortName))
    clusters = os.getenv("CLUSTERS") if os.getenv("CLUSTERS") else args.opts.clusterLists
    csp_token = os.getenv("CSP_TOKEN") if os.getenv("CSP_TOKEN") else args.opts.cspToken
    cluster_type = os.getenv("CLUSTER_TYPE") if os.getenv("CLUSTER_TYPE") else args.opts.clusterType
    onboard = os.getenv("ON_BOARD") if os.getenv("ON_BOARD") else args.opts.onBoard
    csp = CSP(csp_token, log=args.log)

    # clusters = clusters.split(",")
    # while True:
    #     i = 1
    #     gns_config_dict = dict()
    #     domain_name = 'cc-scale-gns-{}.com'.format(i)
    #     for cluster in clusters:
    #         if onboard:
    #             assert prepare_cluster(cluster, log=args.log, cluster_type=cluster_type) == 0, "Failed connecting {}".format(cluster)
    #             args.log.info("onboard cluster {}.".format(cluster))
    #             install_tenant_cluster(csp, cluster, log=args.log)

    #             args.log.info("install istio on cluster {}.".format(cluster))
    #             istio(csp, cluster, 'install', log=args.log)
    #         namespace = "scale-gns-cluster{}-ns ".format(i)
    #         create_namespace(cluster, namespace, log=args.log, cluster_type=cluster_type)
    #         deploy_config(cluster, namespace, i, log=args.log, cluster_type=cluster_type)
    #         args.log("cluster <{}> namespace <{}>".format(cluster, namespace))
    #         gns_config_dict[cluster] = [namespace]
    #     config_gns(csp_token, gns_dict=gns_config_dict, domain_name=domain_name, log=args.log):
    #     i += 1
    #     if i > 3:
    #         break

    domain_name = "gns-2ns-sc.local"
    csp_token = "kJfh2ZsImeLwv3AT7zGuTFTuRv8OpdIkydseLluytz3pdU6rajZBP3aHV1HQoOCW"
    cluster_type = "KIND"
    gns_config_dict = dict()
    gns_config_dict["dd-red-cl1-dev-st"] = ["fortioclient","fortioserver"]
    config_gns(csp_token, gns_dict=gns_config_dict, domain_name=domain_name, log=args.log)
