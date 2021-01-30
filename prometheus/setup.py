# Copyright 2020 VMware, Inc.  All rights reserved. -- VMware Confidential
# Description: config prometheous for service mesh performance
# kubectl create namespace monitoring
# kubectl create -f clusterRole.yaml
# kubectl create -f config-map.yaml
# kubectl create  -f prometheus-deployment.yaml 
# kubectl create -f prometheus-service.yaml --namespace=monitoring
# Disabled: False

import sys
from os.path import dirname, abspath
sys.path.insert(0, dirname(dirname(abspath(__file__))))
from library.utils import *
import traceback
from library.constants import *
from library.kubenertes_utils import *

def install_prometheous(cluster, log=None):
    try:
        cmd = "aws eks update-kubeconfig --name {}".format(cluster)
        rt, out, err = run_local_sh_cmd(cmd)
        if rt != 0:
            log.error("failed updating kubeconfig, err {}".format(err))
            return rt

        try:
            if verify_prometheus(cluster, log=log) == 0:
                log.info("prometheus was installed successfully on {}".format(cluster))
                return 1
        except Exception as e:
            pass

        create_namespace(cluster, PROMETHEUS_NAMESAPCE, log=log)
        context = "{}/{}".format(AWS_EKS_DESC, cluster)
        
        yamls_dir = "{}/manifests".format(dirname(abspath(__file__)))
        cmd = "kubectl --context {} create -f {}/{}".format(context, yamls_dir, "clusterRole.yaml")
        log.info("deploy cluster role {}".format(cmd))
        rt, out, err = run_local_sh_cmd(cmd)
        if rt != 0 and "AlreadyExists" not in err:
            log.error("failed configuring cluster role, err {}".format(err))
            return rt
        
        cmd = "kubectl --context {} create -f {}/{}".format(context, yamls_dir, "config-map.yaml")
        log.info("deploy config map {}".format(cmd))
        rt, out, err = run_local_sh_cmd(cmd)
        if rt != 0 and "AlreadyExists" not in err:
            log.error("failed configuring config map, err {}".format(err))
            return rt
        
        cmd = "kubectl --context {} create -f {}/{}".format(context, yamls_dir, "prometheus-deployment.yaml")
        log.info("deploy prometheus {}".format(cmd))
        rt, out, err = run_local_sh_cmd(cmd)
        if rt != 0 and "AlreadyExists" not in err:
            log.error("failed deploying prometheus, err {}".format(err))
            return rt
        
        cmd = "kubectl --context {} create -f {}/{} ".format(context, yamls_dir, "prometheus-service.yaml")
        log.info("deploy service {}".format(cmd))
        rt, out, err = run_local_sh_cmd(cmd)
        if rt != 0 and "AlreadyExists" not in err:
            log.error("failed deploying prometheus service, err {}".format(err))
            return rt
        
        cmd = "kubectl --context {} create -f {}/{} ".format(context, yamls_dir, "prometheus-gateway.yaml")
        log.info("deploy gateway {}".format(cmd))
        rt, out, err = run_local_sh_cmd(cmd)
        if rt != 0 and "AlreadyExists" not in err:
            log.error("failed deploying prometheus gateway, err {}".format(err))
            return rt
        time.sleep(10)
        return 0
    except Exception as e:
        traceback.print_exc()
        raise

def verify_prometheus(cluster, log=None):
    context = "{}/{}".format(AWS_EKS_DESC, cluster)
    istio_loadbalancer = get_service_loadbalancer(context, ISTIO_NAMESPACE, ISTIO_INGRESSGATEWAY, log=log)
    get_url = "http://{}:{}".format(istio_loadbalancer, EKS_LOADBALANCER_PORT)
    try:
        resp = request(get_url, operation='GET',
                       status_code=[200],
                       verbose_flag=True)
        if "Prometheus Time Series Collection and Processing Server" in resp.text:
            log.info("successfully verify_prometheus {}".format(cluster))
            return 0
    except Exception as ex:
        traceback.format_exc()
        raise
    return 1

def Run(args):
    args.log.info("start testing %s"%(args.shortName))
    cluster = args.opts.clientCluster
    ret = install_prometheous(cluster, log=args.log)
    if ret == 0:
        assert verify_prometheus(cluster, log=args.log) == 0, "Failed verifying prometheus on {}".format(cluster)
