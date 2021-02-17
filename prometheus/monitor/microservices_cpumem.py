# Copyright 2020 VMware, Inc.  All rights reserved. -- VMware Confidential
# Description: config module for service mesh performance
# Group-pods-st: optional
# Disabled: false
# Timeout: 24000


from library.prom import *
from library.fortio import *
from library.kubenertes_utils import *
from datetime import datetime


def Run(args):
    args.log.info("start testing %s"%(args.shortName))
    cluster = os.getenv("CLUSTER") if os.getenv("CLUSTER") else args.opts.singleCluster
    duration = os.getenv("TEST_DURATION") if os.getenv("TEST_DURATION") else args.opts.testDuration
    service_names = os.getenv("SERVICE_NAMES") if os.getenv("SERVICE_NAMES") else args.opts.serviceNames
    name_space = os.getenv("NAME_SPACE") if os.getenv("NAME_SPACE") else args.opts.nameSpace

    prepare_cluster(cluster, log=args.log) == 0, "Failed connecting {}".format(cluster)
    context = "{}/{}".format(AWS_EKS_DESC, cluster)
    promUrl = get_service_loadbalancer(context, ISTIO_NAMESPACE, ISTIO_INGRESSGATEWAY, log=args.log)
    promUrl = "http://{}".format(promUrl)
    duration = 60 * int(duration.strip())
    args.log.info("prom url {} test used time {}".format(promUrl, duration))

    p = prom.Prom(promUrl, duration)
    try:
        service_names = service_names.split(",")
        prom_metrics = p.fetch_tsm_services_cpu_and_mem(name_space, service_names)
        if not prom_metrics:
            print("... Not found")
            raise
        else:
            print("\n\n cpu/memory metrics -- {}".format(prom_metrics))
            file_path = "/var/lib/jenkins/jobs/{}/builds/{}/".format(os.getenv("JOB_NAME"), os.getenv("BUILD_NUMBER"))
            fd = os.open("{}cpu_memory.json".format(file_path), os.O_RDWR|os.O_CREAT)
            out = os.fdopen(fd, "wt")
            # print("dump test results {}".format(json.dumps(test_results)))
            out.write(json.dumps(prom_metrics) + "\n")
            out.close()
            print("")
    except Exception as e:
        traceback.format_exc()
        raise


