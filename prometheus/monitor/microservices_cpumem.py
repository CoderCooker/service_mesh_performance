# Copyright 2020 VMware, Inc.  All rights reserved. -- VMware Confidential
# Description: config module for service mesh performance
# Group-pods-st: optional
# Disabled: false
# Timeout: 24000


from library.prom import *
from library.fortio import *
from datetime import datetime


def Run(args):
    args.log.info("start testing %s"%(args.shortName))
    loop = os.getenv("DURATION")
    promUrl = "http://a4e24f8fde22743679762714c65e805a-255532553.us-west-2.elb.amazonaws.com:80"
    sd = datetime.now()
    prom_start = calendar.timegm(sd.utctimetuple()) + METRICS_START_SKIP_DURATION
    duration = 
    p = prom.Prom(promUrl, duration, start=prom_start)
    try:
        prom_metrics = p.fetch_tsm_services_cpu_and_mem()
        if not prom_metrics:
            print("... Not found")
            raise
        else:
            print("metrics -- ")
            print("")
    except Exception as e:
        traceback.format_exc()
        raise


