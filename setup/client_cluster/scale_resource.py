# Copyright 2020 VMware, Inc.  All rights reserved. -- VMware Confidential
# Description: config module for service mesh performance
# Group-pods-st: optional
# Disabled: false
# Timeout: 24000

from tsm_apis.rest.onoffboard.boardapis import *
from library.kubenertes_utils import *
import threading
from time import sleep
from concurrent.futures import ProcessPoolExecutor
import os
from library.constants import CLIENT_CLUSTER_PREFIX

def generate_loads(name_spaces, istio_loadbalancer, log=None):
    pool = ProcessPoolExecutor(len(name_spaces))    
    for name_space in name_spaces:
        pool.submit(generate_load, (name_space, istio_loadbalancer, log))
        # t = threading.Thread(target=generate_load(name_space=test_name_space, load_balancer=istio_loadbalancer, log=log), name='generate_{}_load'.format(test_name_space), daemon=True)
        # t.start()

def generate_load(name_space='', load_balancer='', log=None):
    generate_load_cmd = 'while :; do curl -HHost:{}.book.com http://{}:80/productpage; sleep 1; done'.format(name_space, load_balancer)
    log.info('generate load cmd {}'.format(generate_load_cmd))     
    run_local_sh_cmd(generate_load_cmd)

def exhaust_cluster_resource(cluster, apps_per_cluster, log=None, cluster_type='EKS', kubeconfig=None):
    log.info("exhausting resources on {}".format(cluster))

    if cluster_type=='EKS':
        context = "{}/{}".format(AWS_EKS_DESC, cluster)
    elif cluster_type.upper()=='KIND':
        context = "kind-{}".format(cluster)

    i = 1
    name_spaces = []
    while i <= apps_per_cluster:
        try:
            test_name_space = "jimin-{}".format(i)
            create_namespace(cluster, test_name_space, log=log, cluster_type=cluster_type, kubeconfig=kubeconfig)

            deploy_app_cmd = "kubectl --context {} -n {} apply -f {}".format(context, test_name_space, SCALE_UP_APP_YAML)
            if kubeconfig:
                deploy_app_cmd = "kubectl --kubeconfig {} -n {} apply -f {}".format(kubeconfig, test_name_space, SCALE_UP_APP_YAML)
            deploy_app_cmd = "{}{}".format(JENKINS_KUBECTL_PREFIX, deploy_app_cmd)
            rt, out, err = run_local_sh_cmd(deploy_app_cmd)
            log.info("deploying bookinfo app on {} rt {} out {} err {}.".format(deploy_app_cmd, rt, out, err))
            assert rt == 0, "Failed deploying bookinfo app on {}, err {}".format(cluster, err)

            ret = wait_for_pods_ready(cluster_name=cluster, context=context, namespace=test_name_space, num_pods=6, cluster_type=cluster_type, kubeconfig=kubeconfig)
            if ret == 1:
                del_namespace_v2(cluster, context, test_name_space, log, kubeconfig=kubeconfig)
                log.info("cluster {} resource has been exhausted.".format(cluster))
                return 0
            name_spaces.append(test_name_space)

            test_name_space = "acme-{}".format(i)
            create_namespace(cluster, test_name_space, log=log, cluster_type=cluster_type, kubeconfig=kubeconfig)

            deploy_app_cmd = "kubectl --context {} -n {} apply -f {}".format(context, test_name_space, MORE_PODS_YAML)
            if kubeconfig:
                deploy_app_cmd = "kubectl --kubeconfig {} -n {} apply -f {}".format(kubeconfig, test_name_space, MORE_PODS_YAML)
            deploy_app_cmd = "{}{}".format(JENKINS_KUBECTL_PREFIX, deploy_app_cmd)
            rt, out, err = run_local_sh_cmd(deploy_app_cmd)
            log.info("deploying acme app on {} rt {} out {} err {}.".format(deploy_app_cmd, rt, out, err))
            assert rt == 0, "Failed deploying bookinfo app on {}, err {}".format(cluster, err)

            ret = wait_for_pods_ready(cluster_name=cluster, context=context, namespace=test_name_space, num_pods=11, cluster_type=cluster_type, kubeconfig=kubeconfig)
            if ret == 1:
                del_namespace_v2(cluster, context, test_name_space, log, kubeconfig=kubeconfig)
                log.info("cluster {} resource has been exhausted.".format(cluster))
                return 0

            if cluster_type.upper() == 'EKS':
                gateway_name = "bookinfo-gateway"
                vs_name = "bookinfo"
                create_gateway(cluster, gateway_name=gateway_name, namespace=test_name_space, hosts=["{}.book.com".format(test_name_space)], log=log, cluster_type=cluster_type)
                create_virtualservice(cluster, vs_name=vs_name, gateway_name=gateway_name, namespace=test_name_space, log=log, cluster_type=cluster_type)
            i += 1
        except Exception as e:
            traceback.format_exc()
            raise

def Run(args):
    args.log.info("start testing %s"%(args.shortName))
    try:
        clusters = os.getenv("CLUSTERS") if os.getenv("CLUSTERS") else args.opts.clusterLists
        csp_token = os.getenv("CSP_TOKEN") if os.getenv("CSP_TOKEN") else args.opts.cspToken
        cluster_type = os.getenv("CLUSTER_TYPE") if os.getenv("CLUSTER_TYPE") else args.opts.clusterType
        clusters_per_tenant = os.getenv("CLUSTER_PER_TENANT") if os.getenv("CLUSTER_PER_TENANT")  else args.opts.clustersNumberPerTenant
        apps_per_cluster = os.getenv("APPS_PER_CLUSTER") if os.getenv("APPS_PER_CLUSTER") else args.opts.appsPerCluster
        clean_up = 'true' if os.getenv("CLEAN_UP") == 'true' else 'false'
        onboard = 'true' if os.getenv("ONBOARD") == 'true' else 'false'
        args.log.info("clusters list {} csp token {} cluster type {} clusters_per_tenant {} apps_per_cluster {} onboard {} cleanup {}".format(clusters, csp_token, cluster_type, clusters_per_tenant, apps_per_cluster,
        onboard, clean_up))

        csp = CSP(csp_token, log=args.log)

        if (not clusters or len(clusters) == 0) and cluster_type.upper() == 'KIND':
            cluster_list = []
            for i in range(int(clusters_per_tenant)):
                cluster_name = "{}-{}".format(CLIENT_CLUSTER_PREFIX, i)
                deploy_kind_cluster_cmd = "{}{}/kind create cluster --name {} --config {}".format(JENKINS_KUBECTL_PREFIX, os.getenv("WORKSPACE"), cluster_name, KIND_CONFIG_FILE)
                args.log.info("Deploying kind cluster {}".format(deploy_kind_cluster_cmd))
                rt, out, err = run_local_sh_cmd(deploy_kind_cluster_cmd)
                args.log.info("kind cluster deploy out {} err {} rt {}".format(out, err, rt))
                try:
                    assert rt == 0, "Failed deploying kind cluster, err {}".format(err)
                except AssertionError as e:
                    if "already exist for a cluster with the name" in err:
                        args.log.info("cluster already created successfully")
                        pass
                    else:
                        traceback.format_exc()
                        raise
                args.log.info("kind cluster {} created successfully".format(cluster_name))
                cluster_list.append(cluster_name)
                cluster_list.append(",")
                print("clusters {}".format(cluster_list))

        if not clusters:
            clusters = ""
            for cluster_name in cluster_list:
                clusters += cluster_name

        clusters = clusters.split(",")
        for cluster in clusters:
            if len(cluster) == 0:
                continue
            kubeconfig = None
            if cluster_type.upper() == 'KIND':
                kubeconfig = prepare_kind_cluster(cluster, log=args.log)
            else:
                assert prepare_cluster(cluster, log=args.log, cluster_type=cluster_type) == 0, "Failed connecting {}".format(cluster)

            if onboard == 'true':
                args.log.info("onboard cluster {}.".format(cluster))
                install_tenant_cluster(csp, cluster, log=args.log, cluster_type=cluster_type, kubeconfig=kubeconfig)

                args.log.info("install istio on cluster {}.".format(cluster))
                istio(csp, cluster, 'install', log=args.log, cluster_type=cluster_type, kubeconfig=kubeconfig)

            exhaust_cluster_resource(cluster, int(apps_per_cluster), log=args.log, cluster_type=cluster_type, kubeconfig=kubeconfig)

            if clean_up == 'true':
                for cluster in clusters:
                    if(len(cluster)==0):
                        continue
                    
                    args.log.info("uninstall istio from cluster {}.".format(cluster))
                    deinit_tenant_cluster(csp, cluster, log=args.log, cluster_type=cluster_type, kubeconfig=kubeconfig)

                    args.log.info("offboard cluster {}.".format(cluster))
                    uninstall_tenant_cluster(csp, cluster, log=args.log, cluster_type=cluster_type, kubeconfig=kubeconfig)

                    if cluster_type.upper() == 'KIND':
                        args.log.info("deleting kind cluster {}".format(cluster))
                        delete_kind_cluster_cmd = "{}{}/kind delete cluster --name {}".format(JENKINS_KUBECTL_PREFIX, os.getenv("WORKSPACE"), cluster)
                        rt, out, err = run_local_sh_cmd(delete_kind_cluster_cmd)
                        print("remove me {} type {} [cmd] {} rt {} out {} err {}".format(cluster, cluster_type.upper(), delete_kind_cluster_cmd,
                        rt, out, err))
                        assert rt == 0, "Failed deleting kind cluster {}, err {}".format(err)
                    else:
                        args.log.info("Currently, performance tests does not recycle EKS cluster.")
    except Exception as e:
            traceback.format_exc()
            raise

