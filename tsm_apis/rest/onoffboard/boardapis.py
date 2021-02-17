# Copyright 2020 VMware, Inc.  All rights reserved. -- VMware Confidential
# Description: config module for service mesh performance
# Group-pods-st: optional
# Disabled: false
# Timeout: 24000

from urllib.parse import urlencode, urlparse
from library.utils import CSP, request
from library.constants import *
from library.kubenertes_utils import *
import sys
import traceback
from tsm_apis.graphql.queries import GraphQLClient, execute_query
from kubernetes import config, client
import tempfile
import os
from prettytable import PrettyTable

def get_operator_deployment_yaml(csp, log=None):
    get_url = "{}/clusters/onboard-url".format(STAGING0_API_ENDPOINT)
    headers = {'csp-auth-token': csp.get_access_token()}
    try:
        response = request(get_url, operation='GET',
                    status_code=[200],
                    csp_url=STAGING_CSP_URL,
                    headers=headers,
                    verbose_flag=True, csp=csp)
        yaml_url = response.json()['url']
        

        response = request(yaml_url, operation='GET',
                    status_code=[200],
                    csp_url=STAGING_CSP_URL,
                    headers=headers,
                    verbose_flag=True, csp=csp)
        return response
    except Exception as ex:
        traceback.format_exc()
        raise

def get_cluster_token(csp, cluster_name, log=None):
    headers = {'csp-auth-token': csp.get_access_token()}
    try:
        put_url = "{}/clusters/{}".format(STAGING0_API_ENDPOINT, cluster_name)
        json_payload = {
                "displayName": cluster_name,
                "description": "",
                "tags": [],
                "labels": [],
                "autoInstallServiceMesh": False,
                "enableNamespaceExclusions": True,
                "namespaceExclusions": []}
        response = request(put_url, operation='PUT',
                    data=json_payload,
                    status_code=[200],
                    csp_url=STAGING_CSP_URL,
                    headers=headers,
                    verbose_flag=True, csp=csp)
        return response.json()["token"]
    except Exception as ex:
        traceback.format_exc()
        raise

def wait_for_with_status(cluster_name, namespace, statuses,
                         num_pods, timeout_in_seconds, context=None,
                         period_in_seconds=DEFAULT_PERIOD,
                         pod_name=None, cluster_type='EKS', kubeconfig=None):
    """Wait until condition is met"""
    if not context:
        if cluster_type=='EKS':
            context = "{}/{}".format(AWS_EKS_DESC, cluster_name)
        elif cluster_type.upper()=='KIND':
            context = "kind-{}".format(cluster_name)
            return wait_for_with_status_v2(cluster_name, namespace, statuses,
                         num_pods, timeout_in_seconds, context=context,
                         period_in_seconds=DEFAULT_PERIOD,
                         pod_name=None, cluster_type=cluster_type, kubeconfig=kubeconfig)
   
    config.load_kube_config(context=context)
    v1 = client.CoreV1Api()
    end_time = time.time() + timeout_in_seconds
    while time.time() < end_time:
        count = 0
        ret = v1.list_namespaced_pod(namespace)
        for i in ret.items:
            if i.status.phase in statuses:
                count += 1
        if count == num_pods:
            print("wait for client pods successfully")
            return 0
        time.sleep(period_in_seconds)
    print("Timed out waiting for %d pods in state %s with %s namespace in cluster %s" % (
            num_pods, str(statuses), namespace, cluster_name))
    ret = v1.list_namespaced_pod(namespace)
    for i in ret.items:
        print("%s -- %s" % (i.metadata.name, i.status.phase))
    return 1

def wait_for_with_status_v2(cluster_name, namespace, statuses,
                         num_pods, timeout_in_seconds, context=None,
                         period_in_seconds=DEFAULT_PERIOD,
                         pod_name=None, cluster_type='EKS', kubeconfig=None):
    """Wait until condition is met"""
    if not context:
        raise Exception("context should not be None")

    end_time = time.time() + timeout_in_seconds
    while time.time() < end_time:
        count = 0
        cmd = '{}kubectl -n vmware-system-tsm get pods | grep -E "Running|Succeeded" | wc -l'.format(JENKINS_KUBECTL_PREFIX)
        if kubeconfig:
            cmd = '{}kubectl --kubeconfig {} -n vmware-system-tsm get pods | grep -E "Running|Succeeded" | wc -l'.format(JENKINS_KUBECTL_PREFIX, kubeconfig)
        rt, out, err = run_local_sh_cmd(cmd)
        print("remove me [cmd] {} rt {} out {} err {} ".format(cmd, rt, out, err))
        assert rt == 0, "Failed getting refresh token rt {}, err {}".format(rt, err)
        count = int(out.strip())
        print("remove me pods number satisfying status {}".format(count))
        if count == num_pods:
            print("wait for client pods successfully")
            return 0
        time.sleep(period_in_seconds)
    print("Timed out waiting for %d pods in state %s with %s namespace in cluster %s" % (
            num_pods, str(statuses), namespace, cluster_name))
    return 1

def wait_for_cluster_ready(csp, client_cluster, log=None, kubeconfig=None):
    """Get client cluster status using graphql queries"""

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

    cluster_ready = False
    count = 100
    query = '''query getClusterStaus($name: String){root { inventory { clusters(name: $name) { name connected domains { name } } } } }'''
    variables = {"name":client_cluster}
    try:
        while not cluster_ready and count > 0:
            r = execute_query(graph_cli, query, variables=variables, log=log, return_content=True)
            print("r {}".format(r))
            json_str = json.loads(r)
            if len(json_str['data']['root']['inventory']['clusters']) > 0:
                c = json_str['data']['root']['inventory']['clusters'][0]
                if c['connected'] and len(c['domains']) > 0:
                    table = PrettyTable()
                    table.field_names = ["Cluster Name", "Domain"]
                    for domain in c["domains"]:
                        table.add_row([client_cluster, domain['name']])
                    print(table)
                    cluster_ready = True
                    break
            count -= 1
            time.sleep(15)
        if not cluster_ready and count == 0:
            return 1
        return 0
    except Exception as e:
        traceback.format_exc()
        log.error("Unable to query client information: ", str(e))
        raise

def install_tenant_cluster(csp, cluster, log=None, cluster_type='EKS', kubeconfig=None):
    cluster_yaml = None
    start_time = time.time()
    try:
        cluster_token = get_cluster_token(csp, cluster, log=log)

        log.info("Getting cluster deployment yaml")
        r = get_operator_deployment_yaml(csp, log=log)
        fd1, cluster_yaml = tempfile.mkstemp()
        with open(cluster_yaml, 'w') as f:
            f.write(r.text)

        context = ""
        if cluster_type=='EKS':
            context = "{}/{}".format(AWS_EKS_DESC, cluster)
        elif cluster_type.upper()=='KIND':
            context = "kind-{}".format(cluster)
        yaml_cmd = ("kubectl --context %s apply -f %s") % (context, cluster_yaml)
        if kubeconfig:
            yaml_cmd = ("kubectl --kubeconfig %s apply -f %s") % (kubeconfig, cluster_yaml)
        yaml_cmd = "{}{}".format(JENKINS_KUBECTL_PREFIX, yaml_cmd)
        rt, out, err = run_local_sh_cmd(yaml_cmd)
        print("remove me apply operator yaml [cmd] {} rt {} out {} err {}".format(yaml_cmd, rt, out, err))
        assert rt == 0, "Failed configuring operator yaml on {}, err {}".format(cluster, err)

        secret_cmd_tmpl = "kubectl --context %s -n %s create secret generic cluster-token --from-literal=token=%s"
        secret_cmd = (secret_cmd_tmpl) % (context, AGENT_NS, cluster_token)
        if kubeconfig:
            secret_cmd_tmpl = "kubectl --kubeconfig %s -n %s create secret generic cluster-token --from-literal=token=%s"
            secret_cmd = (secret_cmd_tmpl) % (kubeconfig, AGENT_NS, cluster_token)
        secret_cmd = "{}{}".format(JENKINS_KUBECTL_PREFIX, secret_cmd)
        rt, out, err = run_local_sh_cmd(secret_cmd)
        print("remove me Injecting token to cluster [cmd] {} rt {} out {} err {}".format(secret_cmd, rt, out, err))
        try:
            assert rt == 0, "Failed injecting token to cluster {}, err {}".format(cluster, err)
        except AssertionError as error:
            if "AlreadyExists" in err:
                return

        log.info("Waiting for pods ready on cluster {}".format(cluster))
        assert wait_for_with_status(cluster, AGENT_NS, ['Running', 'Succeeded'], 3, 960, cluster_type=cluster_type, kubeconfig=kubeconfig) == 0
        
        log.info("Waiting for cluster {} ready".format(cluster))
        assert wait_for_cluster_ready(csp, cluster, log=log, kubeconfig=kubeconfig) == 0, 'Timed out waiting for {} to be in READY state'.format(cluster)
    except Exception as e:
        print("Failed to install tenant cluster: " + str(e))
        traceback.format_exc()
        raise
    finally:
        if cluster_yaml:
            os.remove(cluster_yaml)
    cost = time.time() - start_time
    log.info("\n\nonboard cluster {} ------ {} seconds ------\n\n".format(cluster, cost))
    return cost


def delete_cluster(csp, cluster, log=None, cluster_type='EKS'):
    log.info('delete_cluster {}'.format(cluster))
    headers = {'csp-auth-token': csp.get_access_token()}
    try:
        del_url = "{}/clusters/{}".format(STAGING0_API_ENDPOINT, cluster)
        request(del_url, operation='DELETE',
                    status_code=[202, 404],
                    csp_url=STAGING_CSP_URL,
                    headers=headers,
                    verbose_flag=True, csp=csp)
    except Exception as ex:
        traceback.format_exc()
        raise

    pollT = 1
    while True:
        print('polling delete_cluster')
        try:
            get_url = "{}/clusters/{}".format(STAGING0_API_ENDPOINT, cluster)
            request(del_url, operation='GET',
                    csp_url=STAGING_CSP_URL,
                    headers=headers,
                    verbose_flag=True, csp=csp)
            pollT = pollT + 1
            if pollT > 100:
                raise Exception('delete cluster {} timedout.'.format(cluster))
            time.sleep(10)
        except Exception as ex:
            log.info('cluster {} was deleted successfully.'.format(cluster))
            return 0

def uninstall_tenant_cluster(csp, client_cluster_name, log=None, cluster_type='EKS', kubeconfig=None):
    fd2 = 0
    cluster_yaml = None
    start_time = time.time()
    try:
        log.info("Unregistering cluster {} from SaaS".format(client_cluster_name))
        delete_cluster(csp, client_cluster_name, log=log)

        print("Getting cluster deployment yaml")
        r = get_operator_deployment_yaml(csp, log=log)
        fd2, cluster_yaml = tempfile.mkstemp()
        with open(cluster_yaml, 'w') as f:
            f.write(r.text)

        context = None
        if cluster_type=='EKS':
            context = "{}/{}".format(AWS_EKS_DESC, client_cluster_name)
        elif cluster_type.upper()=='KIND':
            context = "kind-{}".format(client_cluster_name)
        log.info("Deleting cluster components from {}".format(client_cluster_name))
        cmd = ("kubectl --context %s delete -f %s --ignore-not-found=true") % (context, cluster_yaml)
        if kubeconfig:
            cmd = ("kubectl --kubeconfig %s delete -f %s --ignore-not-found=true") % (kubeconfig, cluster_yaml)
        cmd = "{}{}".format(JENKINS_KUBECTL_PREFIX, cmd)
        rt, out, err = run_local_sh_cmd(cmd)
        log.info("[cmd] {} rt {} out {} err {}".format(cmd, rt, out, err))
        assert rt == 0, "Failed Deleting cluster components from {}, err {}".format(client_cluster_name, err)
        assert wait_for_with_status(client_cluster_name, AGENT_NS, ['Running', 'Succeeded'], 0, 60, cluster_type=cluster_type, kubeconfig=kubeconfig) == 0

    except Exception as e:
        traceback.format_exc()
        raise
    finally:
        if fd2:
            os.close(fd2)
        if cluster_yaml:
            os.remove(cluster_yaml)
    cost = time.time() - start_time
    log.info("\n\noffboard cluster {} ------ {} seconds ------\n".format(client_cluster_name, cost))
    return cost

def istio(csp, cluster, operation, tsm_version=None, log=None, cluster_type='EKS', kubeconfig=None):
    start_time = time.time()
    headers = {'csp-auth-token': csp.get_access_token()}
    response = None
    if operation == 'install':
        try:
            get_url = "{}/clusters/{}/apps".format(STAGING0_API_ENDPOINT, cluster)
            response = request(get_url, operation='GET',
                        status_code=[200],
                        csp_url=STAGING_CSP_URL,
                        headers=headers,
                        verbose_flag=True, csp=csp)
            tsm_app = [x for x in response.json() if x.get('id') == 'tsm'][0]
            if tsm_app.get('state') != 'NotInstalled':
                log.info("istio {} already installed on {}".format(tsm_app.get('version'), cluster))
                return 0
        except Exception as ex:
            traceback.format_exc()
            raise
    
    if operation == 'install':
        start_state = "Connected"
        expected_state = "Ready"
    elif operation == 'uninstall':
        start_state = "Ready"
        expected_state = "Connected"

    pollT = 1
    while True:
        try:
            get_url = "{}/clusters/{}".format(STAGING0_API_ENDPOINT, cluster)
            response = request(get_url, operation='GET',
                        status_code=[200],
                        csp_url=STAGING_CSP_URL,
                        headers=headers,
                        verbose_flag=True, csp=csp)
        except Exception as ex:
            traceback.format_exc()
            raise

        try:
            cluster_status = response.json().get("status").get("state")
        except AttributeError as err:
            log.info("failed retrieving cluster {} status err {}".format(cluster, str(err)))
            raise

        if cluster_status == start_state:
            log.info("cluster {} is ready to {} istio".format(cluster, operation))
            break
        elif cluster_status == expected_state:
            log.info("Cluster {} is in desired state. Skipping Istio {}.".format(cluster, operation))
            return 0
        time.sleep(pollT)
        pollT = 3

    tsm_version = tsm_version or "default"
    log.info("Performing istio {} on cluster {} with TSM version {}".format(operation, cluster, tsm_version))

    try:
        if operation == 'install':
            get_url = "{}/clusters/{}/apps/tsm".format(STAGING0_API_ENDPOINT, cluster)
            json_payload = {"version": tsm_version}
            response = request(get_url, operation='PUT',
                        data = json_payload,
                        status_code=[200],
                        csp_url=STAGING_CSP_URL,
                        headers=headers,
                        verbose_flag=True, csp=csp)
        elif operation == 'uninstall':
            delete_url = "{}/clusters/{}/apps/tsm".format(STAGING0_API_ENDPOINT, cluster)
            response = request(get_url, operation='DELETE',
                status_code=[200, 202],
                csp_url=STAGING_CSP_URL,
                headers=headers,
                verbose_flag=True, csp=csp)
    except Exception as ex:
        traceback.format_exc()
        raise

    try:
        job_id = response.json().get("id")
    except AttributeError as err:
        log.error("Failed {} istio, err {}".format(operation, err))
        raise

    pollT = 1
    while True:
        try:
            get_url = "{}/jobs/{}".format(STAGING0_API_ENDPOINT, job_id)
            response = request(get_url, operation='GET',
                        status_code=[200],
                        csp_url=STAGING_CSP_URL,
                        headers=headers,
                        verbose_flag=True, csp=csp)
        except Exception as ex:
            traceback.format_exc()
            raise
        try:
            job_status = response.json().get("state")
            log.info("{} istio job status {}".format(operation, job_status))
            if job_status != "NotStarted":
                break
        except AttributeError as err:
            print("err {} response {}".format(err, response, "{ state }"))
            raise
        time.sleep(pollT)
        pollT = 3

    pollT = 1
    while True:
        try:
            get_url = "{}/clusters/{}".format(STAGING0_API_ENDPOINT, cluster)
            response = request(get_url, operation='GET',
                        status_code=[200, 404],
                        csp_url=STAGING_CSP_URL,
                        headers=headers,
                        verbose_flag=True, csp=csp)
        except Exception as ex:
            traceback.format_exc()
            raise

        try:
            if response and response.json():
                cluster_status = response.json().get("status").get("state")
                log.info("{} istio status {}".format(operation, cluster_status))
                if cluster_status == expected_state:
                    break
            else:
                log.info("responds code 404.")
                break
        except AttributeError as err:
            log.error("failed retrieving cluster {} status err {}".format(cluster, err))
            raise
        time.sleep(pollT)
        pollT = 3

    cost = time.time() - start_time
    log.info("\n\nistio {} {} seconds ------\n\n".format(operation, cost))
    return cost

def check_istio_v2(csp, cluster, log=None, cluster_type='EKS', context=None, kubeconfig=None):
    if not context:
        raise Exception("context should not be none")

    while True:
        try:
            checking_istio_ns_cmd = '{}kubectl --context {} -n vmware-system-tsm get ns istio-system'.format(JENKINS_KUBECTL_PREFIX, context)
            if kubeconfig:
                checking_istio_ns_cmd = '{}kubectl --kubeconfig {} -n vmware-system-tsm get ns istio-system'.format(JENKINS_KUBECTL_PREFIX, kubeconfig)
            rt, out, err = run_local_sh_cmd(checking_istio_ns_cmd)
            print("remove me [cmd] {} rt {} out {} err {}".format(checking_istio_ns_cmd, rt, out, err))
            if rt != 0 or not err:
                return 0
            time.sleep(3)
        except Exception as e:
            traceback.print_exc()
            pass

def deinit_tenant_cluster(csp, cluster, log=None, cluster_type='EKS', kubeconfig=None):
    try:
        context = None
        cost = istio(csp, cluster, 'uninstall', log=log)
        start = time.time()
        if cluster_type=='EKS':
            context = "{}/{}".format(AWS_EKS_DESC, cluster)
        elif cluster_type.upper()=='KIND':
            context = "kind-{}".format(cluster)
            check_istio_v2(csp, cluster, log=None, cluster_type=cluster_type, context=context, kubeconfig=kubeconfig)
            return cost

        config.load_kube_config(context=context)
        v1 = client.CoreV1Api()
        while True:
            try:
                v1.read_namespace("istio-system")
                time.sleep(3)
            except ApiException:
                cost += time.time() - start
                return cost

        return 1
    except AssertionError as e:
        print("Failed to de-init tenant : " + str(e))
        raise

def Run(args):
    args.log.info("start testing %s"%(args.shortName))
    cluster = args.opts.singleCluster
    csp_token = os.getenv("CSP_TOKEN") if os.getenv("CSP_TOKEN") else args.opts.cspToken
    cluster_type = os.getenv("CLUSTER_TYPE") if os.getenv("CLUSTER_TYPE") else args.opts.clusterType
    loop = os.getenv("RestHTTP_ITERATION") if os.getenv("RestHTTP_ITERATION") else args.opts.iterationNumber
    loop = int(loop.strip())
    args.log.info("token {} cluster_type {} loop {}".format(csp_token, cluster_type, loop))

    kubeconfig = None
    if cluster_type.upper() == 'KIND':
        kubeconfig = prepare_kind_cluster(cluster, log=args.log)
    else:
        assert prepare_cluster(cluster, log=args.log, cluster_type=cluster_type) == 0, "Failed connecting {}".format(cluster)
    csp = CSP(csp_token, log=args.log)

    i = 1
    install_cls_count = 0.0
    istio_install_count = 0.0
    uninstall_cls_count = 0.0
    istio_uninstall_count = 0.0
    while True:
        args.log.info("\nonoffboard Loop {}".format(i))
        args.log.info("onboard cluster {}.".format(cluster))
        cost = install_tenant_cluster(csp, cluster, log=args.log, cluster_type=cluster_type, kubeconfig=kubeconfig)
        install_cls_count += cost

        args.log.info("install istio on cluster {}.".format(cluster))
        cost = istio(csp, cluster, 'install', log=args.log, cluster_type=cluster_type, kubeconfig=kubeconfig)
        istio_install_count += cost

        args.log.info("uninstall istio from cluster {}.".format(cluster))
        cost = deinit_tenant_cluster(csp, cluster, log=args.log, cluster_type=cluster_type, kubeconfig=kubeconfig)
        istio_uninstall_count += cost

        args.log.info("offboard cluster {}.".format(cluster))
        cost = uninstall_tenant_cluster(csp, cluster, log=args.log, cluster_type=cluster_type, kubeconfig=kubeconfig)
        uninstall_cls_count += cost
        if i >= loop:
            break
        i += 1
    
    count = loop
    args.log.info("cluster create cost {}".format(install_cls_count/count))
    args.log.info("cluster delete cost {}".format(uninstall_cls_count/count))
    args.log.info("istio install cost {}".format(istio_install_count/count))
    args.log.info("istio uninstall cost {}".format(istio_uninstall_count/count))

