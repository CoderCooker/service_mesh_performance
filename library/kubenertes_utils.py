# Copyright 2020 VMware, Inc.  All rights reserved. -- VMware Confidential
# Description: utility module for service mesh performance
# Disabled: True

import sys
from os.path import dirname, abspath
sys.path.insert(0, dirname(dirname(abspath(__file__))))
from library.utils import *
from library.constants import *
import traceback
from kubernetes import config, client
from time import sleep
import time
from pprint import pprint
from kubernetes.client.exceptions import ApiException
from pathlib import Path
import os

def del_namespace(cluster, context, namespace, log=None, kubeconfig=None):
    assert len(namespace.strip()) > 0, "namespace should not be none or empty."
    try:
        config.load_kube_config(context=context)
        v1 = client.CoreV1Api()

        if [name for name in v1.list_namespace().items if namespace == name.metadata.name]:
            log.info("deleting {} existing namespace {} ".format(cluster, namespace))
            v1.delete_namespace(name=namespace, body=client.V1DeleteOptions())
            i = 0
            while True:
                if not [name for name in v1.list_namespace().items if namespace == name.metadata.name]:
                    break
                sleep(5)
                i += 1
                if i > 100:
                    raise Exception("failed deleting existing namespace {} on {}".format(namespace, cluster))
        return 0
    except Exception as e:
        traceback.format_exc()
        raise

def del_namespace_v2(cluster, context, namespace, log, kubeconfig=None):
    assert len(namespace.strip()) > 0, "namespace should not be none or empty."
    assert len(context) > 0, "context should not be none or empty"
    try:
        cmd = "{}kubectl --context {} get ns {}".format(JENKINS_KUBECTL_PREFIX, context, namespace)
        if kubeconfig:
            cmd = "{}kubectl --kubeconfig {} get ns {}".format(JENKINS_KUBECTL_PREFIX, kubeconfig, namespace)
        rt, out, err = run_local_sh_cmd(cmd)
        print("get ns [cmd] {} rt {} out {} err {}".format(cmd, rt, out, err))
        if rt != 0:
            print("failed reading namespace err {}".format(err))
            return
        if(len(out) > 0 or len(err) > 0):
            cmd = "{}kubectl --context {} delete ns {}".format(JENKINS_KUBECTL_PREFIX, context, namespace)
            if kubeconfig:
                cmd = "{}kubectl --kubeconfig {} delete ns {}".format(JENKINS_KUBECTL_PREFIX, kubeconfig, namespace)
            rt, out, err = run_local_sh_cmd(cmd)
            print("delete ns [cmd] {} rt {} out {} err {}".format(cmd, rt, out, err))
            if rt != 0:
                print("failed deleting namespace err {}".format(err))
                raise

            while True:
                cmd = "{}kubectl --context {} get ns {} ".format(JENKINS_KUBECTL_PREFIX, context, namespace)
                if kubeconfig:
                    cmd = "{}kubectl --kubeconfig {} get ns {} ".format(JENKINS_KUBECTL_PREFIX, kubeconfig, namespace)
                rt, out, err = run_local_sh_cmd(cmd)
                print("verifying deleting ns [cmd] {} rt {} out {} err {}".format(cmd, rt, out, err))
                if rt != 0 and "not found" in err:
                    print("Successfully deleted namespace {} from cluster {}".format(namespace, cluster))
                    break
                sleep(5)
                i += 1
                if i > 100:
                    raise Exception("failed deleting existing namespace {} on {}".format(namespace, cluster))

        else:
            print("namespace {} does not exist on cluster {}".format(namespace, cluster))
        return 0
    except Exception as e:
        traceback.format_exc()
        raise

def create_namespace_v2(cluster, namespace, log=None, cluster_type='EKS', context=None, kubeconfig=None):
    if not context:
        raise Exception("context should not be None.")
    try:
        del_namespace_v2(cluster, context, namespace, log, kubeconfig=kubeconfig)
        cmd = "{}kubectl --context {} create ns {}".format(JENKINS_KUBECTL_PREFIX, context, namespace)
        if kubeconfig:
            cmd = "{}kubectl --kubeconfig {} create ns {}".format(JENKINS_KUBECTL_PREFIX, kubeconfig, namespace)
        rt, out, err = run_local_sh_cmd(cmd)
        print("creating ns [cmd] {} rt {} out {} err {}".format(cmd, rt, out, err))
        if rt != 0:
            raise Exception("failed creating namespace err {}".format(err))
        
        while True:
            cmd = "{}kubectl --context {} get ns {}".format(JENKINS_KUBECTL_PREFIX, context, namespace)
            if kubeconfig:
                cmd = "{}kubectl --kubeconfig {} get ns {}".format(JENKINS_KUBECTL_PREFIX, kubeconfig, namespace)
            rt, out, err = run_local_sh_cmd(cmd)
            print("verifying creating ns [cmd] {} rt {} out {} err {}".format(cmd, rt, out, err))
            if rt != 0:
                print("failed verifying creating namespace err {}".format(err))
                raise Exception("failed verifying creating namespace err {}".format(err))
            if((namespace in out and 'Active' in out) or (namespace in err and 'Active' in err)):
                print("Successfully created namespace {} on cluster {}".format(namespace, cluster))
                break
            sleep(5)
            i += 1
            if i > 100:
                raise Exception("timed out while creating namespace {}".format(namespace))
    except Exception as e:
        traceback.format_exc()
        raise

def create_namespace(cluster, namespace, log=None, cluster_type='EKS', kubeconfig=None):
    assert len(namespace.strip()) > 0, "namespace should not be none or empty."
    log.info("creating namespace {} on cluster {}".format(namespace, cluster))
    try:
        context = None
        if cluster_type=='EKS':
            context = "{}/{}".format(AWS_EKS_DESC, cluster)
        elif cluster_type.upper()=='KIND':
            context = "kind-{}".format(cluster)
            return create_namespace_v2(cluster, namespace, log=log, cluster_type=cluster_type, context=context, kubeconfig=kubeconfig)

        config.load_kube_config(context=context)
        v1 = client.CoreV1Api()

        del_namespace(cluster, context, namespace, log, kubeconfig=kubeconfig)

        body = client.V1Namespace()
        body.metadata = client.V1ObjectMeta(name=namespace)
        v1.create_namespace(body)
        i = 0
        while True:
            if [name for name in v1.list_namespace().items if namespace == name.metadata.name]:
                log.info("namespace {} created successfully on {}".format(namespace, cluster))
                break
            sleep(5)
            i += 1
            if i > 100:
                raise Exception("timed out while creating namespace {}".format(namespace))
    except Exception as e:
        traceback.print_exc()
        raise

def get_service_loadbalancer(context, namespace, service_name, log=None):
    ip_loc = "{.status.loadBalancer.ingress[0].hostname}"
    parse_external_ip_cmd = "kubectl --context %s -n %s get services %s -o jsonpath=\"%s\"" % (context, namespace, service_name, ip_loc)
    if log:
        log.info("get svc loadbalancer cmd: {}".format(parse_external_ip_cmd))
    rt, out, err = run_local_sh_cmd(parse_external_ip_cmd)
    if rt != 0:
        raise Exception("failed reading loadbalancer err {}".format(err))
    if not out.strip():
        raise Exception("failed getting {} loadbalancer".format(service_name))
    load_balancer = out.strip()
    if log:
        log.info("{} host {}".format(service_name, load_balancer))
    return load_balancer

def get_pod(cluster, namespace, pod_regex, log=None):
    try:
        if cluster_type=='EKS':
            context = "{}/{}".format(AWS_EKS_DESC, cluster)
        elif cluster_type=='Kind':
            context = "kind-{}".format(cluster)
        config.load_kube_config(context=context)
        v1 = client.CoreV1Api()
        ret = v1.list_namespaced_pod(namespace)
        for item in ret.items:
            if item.status.phase == 'Running' and pod_regex in item.metadata.name:
                if log:
                    log.info("pod {} status {}".format(item.metadata.name, item.status.phase))
                return item.metadata.name
    except Exception as e:
        traceback.print_exc()
        raise

def scale_pod(cluster, namespace, deployment, pod_num, log=None, cluster_type='EKS'):
    try:
        if cluster_type=='EKS':
            context = "{}/{}".format(AWS_EKS_DESC, cluster)
        elif cluster_type=='Kind':
            context = "kind-{}".format(cluster)

        scale = "kubectl --context {} -n {} scale deployments {} --replicas={}".format(context, namespace, deployment, pod_num)
        log.info("scale {}".format(scale))
        rt, out, err = run_local_sh_cmd(scale)
        if rt != 0:
            raise Exception("failed scaling {} err {}".format(deployment, err))
        config.load_kube_config(context=context)
        v1 = client.CoreV1Api()
        i = 0
        while True:
            ret = v1.list_namespaced_pod(namespace)
            ready = True
            for pod in ret.items:
                if pod.status.phase != "Running":
                    ready = False
            if ready:
                break
            i += 1
            if i > 100:
                raise Exception("failed scaling {} to {}".format(deployment, pod_num))
            time.sleep(6)
    except Exception as e:
        traceback.format_exc()
        raise
    
    wait_for_pods_ready(cluster_name=cluster, context=context, namespace=namespace, num_pods=pod_num, kubeconfig=None)
    if log:
        log.info("Successfully scale {} to {}".format(deployment, pod_num))

    wait_while_populating_to_tsm(pod_num)

def prepare_kind_cluster(client_cluster, log=None):
    try:
        cur_dir = os.getenv("WORKSPACE")
        file_id = generate_randoms()
        tmp_kube_config = "{}/{}".format(cur_dir, file_id)
        cmd = "echo \'jenkins\' | sudo -S {}/kind get kubeconfig --name={} >> {}".format(cur_dir, client_cluster, tmp_kube_config)
        rt, out, err = run_local_sh_cmd(cmd)
        log.info("getting kind cluster {} configuration file [cmd] {} rt {} out {} err {}".format(client_cluster, cmd, rt, out, err))
        assert rt == 0, "Failed executing {}, err {}".format(cmd, err)
        file_size = Path(tmp_kube_config).stat().st_size
        if(file_size < 100):
            raise Exception("failed getting {} kubeconfig, err size {}".format(tmp_kube_config, file_size)) 
        return tmp_kube_config
    except Exception as e:
        traceback.format_exc()
        raise

def prepare_cluster(client_cluster, log=None, cluster_type='EKS'):
    try:
        if cluster_type=='EKS':
            cmd = "aws eks update-kubeconfig --name {}".format(client_cluster)
            rt, out, err = run_local_sh_cmd(cmd)
            if rt != 0:
                log.error("failed connecting {}, err {}".format(client_cluster, err))
                return rt
            return 0
        elif cluster_type.upper()=='KIND':
            return prepare_kind_cluster(client_cluster, log=log)
        else:
            cmd = "echo \'jenkins\' | sudo -S cat ~/.kube/config"
            rt, out, err = run_local_sh_cmd(cmd)
            log.info("[cmd] {} out {} err {} rt {}".format(cmd, out, err, rt))
            if rt != 0:
                log.error("failed connecting {}, err {}".format(client_cluster, err))
                return rt

            cmd = "echo \'jenkins\' | sudo -S kubectl config get-contexts | grep \"{}\"".format(client_cluster)
            rt, out, err = run_local_sh_cmd(cmd)
            log.info("[cmd] {} out {} err {} rt {}".format(cmd, out, err, rt))
            if rt != 0:
                log.error("atm failed connecting {}, err {}".format(client_cluster, err))
            elif len(out) > 0:
                log.info("cluster {} context already loaded.".format(client_cluster))
                cmd = "echo \'jenkins\' | sudo -S kubectl config use-context kind-{}".format(client_cluster)
                rt, out, err = run_local_sh_cmd(cmd)
                log.info("using cluster {} context [cmd] {} rt {} out {} err {}".format(client_cluster, cmd, rt, out, err))
                if rt != 0:
                    log.error("failed switching to kind cluster {} context, err {}".format(client_cluster, err))
                    return rt
                else:  
                    cmd = "echo \'jenkins\' | sudo -S kubectl get ns"
                    rt, out, err = run_local_sh_cmd(cmd)
                    log.info("verifying cluster {} context [cmd] {} rt {} out {} err {}".format(client_cluster, cmd, rt, out, err))
                    if rt != 0:
                        log.error("failed connecting to kind cluster {}, err {}".format(client_cluster, err))
                        return rt
                return 0
            else:
                log.info("Loading cluster {} context.".format(client_cluster))

            cur_dir = os.getenv("WORKSPACE")
            tmp_kube_config = "{}/cluster.config".format(cur_dir)
            log.info("temp kube config {}".format(tmp_kube_config))
            if not os.path.exists(tmp_kube_config):
                os.mknod(tmp_kube_config)
            tmp_kube_config_file_size = Path(tmp_kube_config).stat().st_size
            if tmp_kube_config_file_size > 0:
                log.info("tmp_kube_config {} size {} emptying it.".format(tmp_kube_config, tmp_kube_config_file_size))
                open(tmp_kube_config, 'w').close()

            cmd = "echo \'jenkins\' | sudo -S {}/kind get kubeconfig --name={} >> {}".format(cur_dir, client_cluster, tmp_kube_config)
            log.info("getting kind cluster {} configuration file [cmd] {}".format(client_cluster, cmd))
            rt, out, err = run_local_sh_cmd(cmd)
            assert rt == 0, "Failed executing {}, err {}".format(cmd, err)
            kind_cluster_config_file_size = Path(tmp_kube_config).stat().st_size
            log.info("temp kube config {} size {}".format(tmp_kube_config, kind_cluster_config_file_size))
            if kind_cluster_config_file_size < 100:
                raise "failed getting kind cluster {} configuration file".format(client_cluster)

            random = generate_randoms()
            temp_merge_config = "{}/{}".format(cur_dir, random)
            log.info("temp merge config {}".format(temp_merge_config))
            if not os.path.exists(temp_merge_config):
                os.mknod(temp_merge_config)

            cmd = "echo \'jenkins\' | sudo -S KUBECONFIG=~/.kube/config:{} kubectl config view --merge --flatten > {} && echo \'jenkins\' | sudo -S mv {} ~/.kube/config".format(tmp_kube_config, temp_merge_config, temp_merge_config)
            log.info("merging cluster {} configuration file [cmd] {}".format(client_cluster, cmd))
            rt, out, err = run_local_sh_cmd(cmd)
            if rt != 0:
                log.error("failed merging kind cluster configuration file {}, err {}".format(client_cluster, err))

            cmd = "{}kubectl config use-context kind-{}".format(JENKINS_KUBECTL_PREFIX, client_cluster)
            log.info("using cluster {} context [cmd] {}".format(client_cluster, cmd))
            rt, out, err = run_local_sh_cmd(cmd)
            if rt != 0:
                log.error("failed switching to kind cluster {} context, err {}".format(client_cluster, err))
                return rt
            
            cmd = "{}kubectl get ns".format(JENKINS_KUBECTL_PREFIX)
            log.info("verifying cluster {} context [cmd] {}".format(client_cluster, cmd))
            rt, out, err = run_local_sh_cmd(cmd)
            if rt != 0:
                log.error("failed connecting to kind cluster {}, err {}".format(client_cluster, err))
                return rt

            return 0
    except Exception as e:
        traceback.format_exc()
        raise

def wait_for_pods_ready_v2(cluster_name=None, context=None, namespace=None, statuses=["Running"], num_pods=None, cluster_type='KIND', kubeconfig=None):
    try:
        end_time = time.time() + 1000
        period_in_seconds = 10
        while time.time() < end_time:
            cmd = "{}kubectl --context {} -n {} get pods | grep \"Running\" | wc -l".format(JENKINS_KUBECTL_PREFIX, context, namespace)
            if kubeconfig:
                cmd = "{}kubectl --kubeconfig {} -n {} get pods | grep \"Running\" | wc -l".format(JENKINS_KUBECTL_PREFIX, kubeconfig, namespace)
            rt, out, err = run_local_sh_cmd(cmd)
            print("checking pods status [cmd] {} rt {} out {} err {}".format(cmd, rt, out, err))
            if rt != 0:
                raise Exception("failed checking pods on cluster {}, err {}".format(client_cluster, err))
            count = int(out.strip())
            print("current running number {} target {}".format(count, num_pods))
            if count == num_pods:
                print("all pods are in expected status.")
                return 0
            time.sleep(period_in_seconds)
        print("Timed out waiting for %d pods in state %s with %s namespace in cluster %s" % (
                num_pods, str(statuses), namespace, cluster_name))
        cmd = "{}kubectl --context {} -n {} get pods".format(JENKINS_KUBECTL_PREFIX, context, namespace)
        if kubeconfig:
            cmd = "{}kubectl --kubeconfig {} -n {} get pods".format(JENKINS_KUBECTL_PREFIX, kubeconfig, namespace)
        rt, out, err = run_local_sh_cmd(cmd)
        print("timeout checking pods status [cmd] {} rt {} out {} err {}".format(cmd, rt, out, err))
        if rt != 0:
            raise Exception("failed checking pods on cluster {}, err {}".format(client_cluster, err))
        return 1
    except Exception as e:
        traceback.format_exc()
        raise
    return 0
 
# fix me
def wait_for_pods_ready(cluster_name=None, context=None, namespace=None, statuses=["Running"], pod_name=None, num_pods=None, cluster_type='EKS', kubeconfig=None):
    if(cluster_type.upper() == 'KIND'):
        print("kind cluster. workaround kubeapi temporarily.")
        return wait_for_pods_ready_v2(cluster_name=cluster_name, context=context, namespace=namespace, statuses=["Running"], num_pods=num_pods, cluster_type='KIND', kubeconfig=kubeconfig)
    config.load_kube_config(context=context)
    v1 = client.CoreV1Api()
    end_time = time.time() + 240
    period_in_seconds = 10
    while time.time() < end_time:
        count = 0
        ret = v1.list_namespaced_pod(namespace)
        for i in ret.items:
            if pod_name is None:
                if i.status.phase in statuses:
                    count += 1
            else:
                if re.search(pod_name, i.metadata.name) and \
                        i.status.phase in statuses:
                    count += 1
        if count == num_pods:
            return 0
        time.sleep(period_in_seconds)
    if pod_name:
        print("Timed out waiting for pod %s in state %s with %s namespace in cluster %s" % (
              pod_name, str(statuses), namespace, cluster_name))
    else:
        print("Timed out waiting for %d pods in state %s with %s namespace in cluster %s" % (
              num_pods, str(statuses), namespace, cluster_name))
        ret = v1.list_namespaced_pod(namespace)
        for i in ret.items:
            print("%s -- %s" % (i.metadata.name, i.status.phase))
    return 1

def create_virtualservice(cluster, vs_name="my_vs_name", gateway_name='my_gateway', namespace='default', log=None, cluster_type='EKS'):
    context = None
    if cluster_type=='EKS':
        context = "{}/{}".format(AWS_EKS_DESC, cluster)
    elif cluster_type.upper()=='KIND':
        context = "kind-{}".format(cluster)
    else:
        raise Exception("unknown cluster type {} yet.".format(cluster_type))

    try:
        config.load_kube_config(context=context)
        api = client.CustomObjectsApi()
        my_vs = {
  "apiVersion": "{}/{}".format(KUBERNETES_ISTIO_NETWORK_GROUP, KUBERNETES_ISTIO_NETWORK_VERSION),
  "kind": "VirtualService",
  "metadata": {
    "name": "{}".format(vs_name),
    "namespace": "{}".format(namespace)
  },
  "spec": {
    "hosts": [
      "{}.book.com".format(namespace)
    ],
    "gateways": [
      "{}".format(gateway_name)
    ],
    "http": [
      {
        "match": [
          {
            "uri": {
              "exact": "/productpage"
            }
          },
          {
            "uri": {
              "prefix": "/static"
            }
          },
          {
            "uri": {
              "prefix": "/login"
            }
          },
          {
            "uri": {
              "prefix": "/logout"
            }
          },
          {
            "uri": {
              "prefix": "/api/v1/products"
            }
          }
        ],
        "route": [
          {
            "destination": {
              "host": "productpage",
              "port": {
                "number": 9080
              }
            }
          }
        ]
      }
    ]
  }
}
        api.create_namespaced_custom_object(
            group=KUBERNETES_ISTIO_NETWORK_GROUP,
            version=KUBERNETES_ISTIO_NETWORK_VERSION,
            namespace=namespace,
            plural=KUBERNETES_ISTIO_VIRTUAL_SERVICE_PLURALS,
            body=my_vs
        )

    except ApiException as err:
        if "Conflict" in err.reason:
            pass
        else:
            log.error(err)
            raise
    except Exception as e:
        traceback.format_exc()
        raise

    resource = api.get_namespaced_custom_object(
        name=vs_name,
        group=KUBERNETES_ISTIO_NETWORK_GROUP,
        version=KUBERNETES_ISTIO_NETWORK_VERSION,
        namespace=namespace,
        plural=KUBERNETES_ISTIO_VIRTUAL_SERVICE_PLURALS
    )
    pprint(resource)
    return 0

def delete_gateway(cluster, gateway_name='my_gateway', namespace='default', log=None):
    context = "{}/{}".format(AWS_EKS_DESC, cluster)
    try:
        config.load_kube_config(context=context)
        api = client.CustomObjectsApi()
        api.delete_namespaced_custom_object(
            group=KUBERNETES_ISTIO_NETWORK_GROUP,
            version=KUBERNETES_ISTIO_NETWORK_VERSION,
            name=gateway_name,
            namespace=namespace,
            plural=KUBERNETES_ISTIO_GATEWAY_PLURAL,
            body=client.V1DeleteOptions(),
        )
        log.info("gateway {} deleted".format(gateway_name))
    except Exception as e:
        traceback.format_exc()
        raise

def create_gateway(cluster, gateway_name='my_gateway', namespace='default', hosts=["*"], log=None, cluster_type='EKS'):
    context = None
    if cluster_type=='EKS':
        context = "{}/{}".format(AWS_EKS_DESC, cluster)
    elif cluster_type.upper()=='KIND':
        context = "kind-{}".format(cluster)
    else:
        raise Exception("unknown cluster type {} yet.".format(cluster_type))
    try:
        config.load_kube_config(context=context)
        api = client.CustomObjectsApi()

        my_gateway = {
    "apiVersion": "{}/{}".format(KUBERNETES_ISTIO_NETWORK_GROUP, KUBERNETES_ISTIO_NETWORK_VERSION),
    "kind": "Gateway",
    "metadata": {
        "name": gateway_name,
        "namespace": "{}".format(namespace)
    },
    "spec": {
        "selector": {
        "istio": "ingressgateway"
        },
        "servers": [
        {
            "port": {
            "number": 80,
            "name": "http",
            "protocol": "HTTP"
            },
            "hosts": hosts
        }
        ]
    }
    }

        api.create_namespaced_custom_object(
            group=KUBERNETES_ISTIO_NETWORK_GROUP,
            version=KUBERNETES_ISTIO_NETWORK_VERSION,
            namespace=namespace,
            plural=KUBERNETES_ISTIO_GATEWAY_PLURAL,
            body=my_gateway
        )
        log.info("gateway {} created".format(my_gateway))
    except ApiException as err:
        if "Conflict" in err.reason:
            pass
        else:
            log.error(err)
            raise
    except Exception as e:
        traceback.format_exc()
        raise

    resource = api.get_namespaced_custom_object(
        name=gateway_name,
        group=KUBERNETES_ISTIO_NETWORK_GROUP,
        version=KUBERNETES_ISTIO_NETWORK_VERSION,
        namespace=namespace,
        plural=KUBERNETES_ISTIO_GATEWAY_PLURAL
    )
    pprint(resource)

def create_deployment(domain_name=None, namespace=None, context=None):
    try:
        config.load_kube_config(context=context)
        apps_v1 = client.AppsV1Api()
        deployment = create_deployment_object(domain_name)
      
        # Create deployement
        api_response = apps_v1.create_namespaced_deployment(
            body=deployment,
            namespace=namespace)
        print("Deployment created. status='%s'" % str(api_response.status))        
    except ApiException as err:
        traceback.format_exc()
        raise

def create_deployment_object(domain_name=None):
    DEPLOYMENT_NAME = "productpage-v1"
    # Configureate Pod template container
    
    container = client.V1Container(
        name="productpage",
        image="docker.io/istio/examples-bookinfo-productpage-v1:1.16.2",
        image_pull_policy="IfNotPresent",

        env=[client.V1EnvVar(name="DETAILS_HOSTNAME", value='details.{}'.format(domain_name)),
        client.V1EnvVar(name="RATINGS_HOSTNAME", value='ratings.{}'.format(domain_name)),
        client.V1EnvVar(name="REVIEWS_HOSTNAME", value='reviews.{}'.format(domain_name))
        ],

        ports=[client.V1ContainerPort(container_port=9080)],
        volume_mounts=[client.V1VolumeMount(name="tmp", mount_path='/tmp')],
    )

    volume = client.V1Volume(
        name = "tmp",
        empty_dir = {},
    )

    # Create and configurate a spec section
    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"app": "productpage","version":"v1"}),
        spec=client.V1PodSpec(containers=[container],volumes=[volume]))

    # Create the specification of deployment
    spec = client.V1DeploymentSpec(
        replicas=1,
        template=template,
        selector={'matchLabels': {'app': 'productpage',"version":"v1"}})

    # Instantiate the deployment object
    deployment = client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(name=DEPLOYMENT_NAME),
        spec=spec)

    return deployment

def create_productpage_service(context=None, name_space=None, service_name=None):
    manifest = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata":{
            "name": "{}".format(service_name),
            "labels":{
                "app": "{}".format(service_name)
                "service": "{}".format(service_name)
            }
        },
        "spec":{
            "ports":[
                {
                    "port": "9080",
                    "name": "http"
                }
            ],
            "selector":{
                "app": "productpage",
                "version": "v1"
            }
        }
    }

    try:
        config.load_kube_config(context=context)
        api_instance = client.CoreV1Api()
        api_response = api_instance.create_namespaced_service(name_space, manifest, pretty='true')
        pprint(api_response)
    except ApiException as e:
        print("Exception when calling CoreV1Api->create_namespaced_endpoints: %s\n" % e)
