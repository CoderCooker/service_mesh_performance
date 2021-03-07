# Copyright 2020 VMware, Inc.  All rights reserved. -- VMware Confidential
# Description: config module for service mesh performance
# Group-pods-st: optional
# Disabled: false
# Timeout: 24000

from tsm_apis.rest.onoffboard.boardapis import *
from tsm_apis.rest.gns.apis import check_gns_availability
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

def check_gns_service(context, namespace, domain_name, log=None, start=None):
    log.info('check services')
    get_pods_cmd = 'kubectl --context {} -n {} get pods | grep sleep'.format(context, namespace)
    rt, out, err = run_local_sh_cmd(get_pods_cmd)
    assert rt == 0, "Failed get sleep pods err {}".format(err)
    log.info("get pods {} rt {} out {} err {}.".format(get_pods_cmd, rt, out, err))
    sleep_pod = out.split()[0].strip()
    count = 1
    while True:
        check_cmd = 'kubectl --context {} -n {} exec -i {}  -c sleep -- sh -c \'curl http://productpage.{}:9080/productpage | grep \'Book Details\'\''.format(context, namespace, sleep_pod, domain_name)
        log.info("check services availability cmd {}".format(check_cmd))
        try:
            rt, out, err = run_local_sh_cmd(check_cmd)
            #assert rt == 0, "Failed checking services err {}".format(err)
            if rt != 0:
                count = count + 1
                if count > 100:
                    raise
                time.sleep(3)
                continue
            log.info("checking services  rt {} out {} err {}.".format(rt, out, err))
            if 'Book Details' in out.strip():
                end = time.time()
                response_time = end - start + count * 3
                log.info("product already retrieve book details from details serivce through GNS within {} seconds.".format(response_time))
                if response_time > 30:
                    raise("touch TSM limits.")
                else:
                    return
            time.sleep(1)
        except Exception as e:
            count = count + 1
            if count > 100:
                raise
            time.sleep(3)
            continue
        


def Run(args):
    args.log.info("start testing %s"%(args.shortName))
    csp_token = os.getenv("CSP_TOKEN") if os.getenv("CSP_TOKEN") else args.opts.cspToken
    clusters = os.getenv("CLUSTERS") if os.getenv("CLUSTERS") else args.opts.clusterLists
    gns_total = os.getenv("GNS_TOTAL") if os.getenv("GNS_TOTAL") else args.opts.iterationNumber
    gns_total = int(gns_total.strip())


    clusters = clusters.split(",")
    for cluster in clusters:
        assert prepare_cluster(cluster, log=args.log) == 0, "Failed connecting {}".format(cluster)

    gns = GNS(csp_token, log=args.log)
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

    i = 1
    while i <= gns_total:
        # create_namespaces
        random_num = ''.join(random.choices(string.ascii_lowercase + string.digits, k = 6))
        test_name_space = "tsmperf-{}".format(random_num)
        for cluster in clusters:
            create_namespace(cluster, test_name_space, log=args.log)

        # deploy_services, deploy load generator
        cls1_context = "{}/{}".format(AWS_EKS_DESC, clusters[0])
        for cls_1_yaml in GNS_VERIFICATION_CLS1_YAMLS:
            deploy_service = "kubectl --context {} -n {} apply -f {}".format(cls1_context, test_name_space, cls_1_yaml)
            args.log.info("deploying to cls1 {}".format(deploy_service))
            rt, out, err = run_local_sh_cmd(deploy_service)
            args.log.info("deploying yaml {} on {} rt {} out {} err {}.".format(cls_1_yaml, clusters[0], rt, out, err))
            assert rt == 0, "Failed deploying {} yaml on cluster 1 {}, err {}".format(cls_1_yaml, clusters[0], err)
      
        domain_name = "{}.local".format(test_name_space)
        create_deployment(domain_name=domain_name, namespace=test_name_space, context=cls1_context)

        cls2_context = "{}/{}".format(AWS_EKS_DESC, clusters[1])
        for cls_2_yaml in GNS_VERIFICATION_CLS2_YAMLS:
            deploy_service = "kubectl --context {} -n {} apply -f {}".format(cls2_context, test_name_space, cls_2_yaml)
            args.log.info("deploying to cls2 {}".format(deploy_service))
            rt, out, err = run_local_sh_cmd(deploy_service)
            args.log.info("deploying yaml {} on {} rt {} out {} err {}.".format(cls_2_yaml, clusters[1], rt, out, err))
            assert rt == 0, "Failed deploying {} yaml on cluster 2 {}, err {}".format(cls_2_yaml, clusters[1], err)

        # create GNS generate load from shopping to services users/cart/catalog/order
        gns_config_dict = dict()
        gns_config_dict[clusters[1]] = [test_name_space]
        gns_config_dict[clusters[0]] = [test_name_space]

        gns_name = ''.join(random.choices(string.ascii_lowercase + string.digits, k = 6))
        start = time.time()
        try:
            gns_obj = gns.save(gns_config_dict, domain_name, gns_name=gns_name)
        except Exception as e:
            raise
        check_gns_service(cls1_context, test_name_space, domain_name, log=args.log, start=start)
        # check_gns_availability(graph_cli, gns_name=gns_name, log=args.log, start=start)
        i += 1

    # domain_name = "gns-2ns-sc.local"
    # csp_token = ""
    # gns_config_dict = dict()
    # gns_config_dict["dd-red-cl1-dev-st"] = ["fortioclient","fortioserver"]
    # config_gns(csp_token, gns_dict=gns_config_dict, domain_name=domain_name, log=args.log)
