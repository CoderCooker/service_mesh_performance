# Copyright 2020 VMware, Inc.  All rights reserved. -- VMware Confidential
# Description: config module for service mesh performance
# Group-pods-st: optional
# Disabled: false
# Timeout: 24000

from library.utils import *
from library.constants import *
from library.kubenertes_utils import *

import traceback
from library.utils import CSP, request
from library.gns_utils import GNS

def psv_apis(client_cluster, gns, log=None):
    name = ''.join(random.choices(string.ascii_lowercase + string.digits, k = 6))
    try:
    
       create_namespace(client_cluster, name, log)
       gns_config_dict = dict()
       gns_config_dict[client_cluster] = [name]
       gns.save(gns_config_dict, 'acme.com', name)

       resp = gns.create_external_account(name)
       external_accounts_id = resp['id']
       
       resp = gns.create_external_dns(name, external_accounts_id)
       ext_dns_id = resp['id']
       
       sub_dom = "tsm-perf-create-http-pub-svc-{}".format(name)
       psv_config = gns.config_psv(ext_dns_id, name, sub_dom)

       fqdn= "tsm-perf-create-http-pub-svc-{}.servicemesh.biz".format(name)
       resp = gns.create_psv(name, fqdn, psv_config)
       
       #gns.delete_pvs(name, fqdn)
    except Exception as e:
        traceback.format_exc()
        raise     

def gns_apis(client_cluster, gns, log=None):
    try:
        namespace = ''.join(random.choices(string.ascii_lowercase + string.digits, k = 5))
        namespace = "tsm-perf-resthttp-ns-{}".format(namespace)
        create_namespace(client_cluster, namespace, log=log)
        
        gns_config_dict = dict()
        gns_config_dict[client_cluster] = [namespace]
        gns_name = ''.join(random.choices(string.ascii_lowercase + string.digits, k = 6))
        gns_obj = gns.save(gns_config_dict, '{}.local'.format(namespace), gns_name=gns_name)
        gns.get(gns_name)
        gns.list_gns()
        gns.delete(gns_name)
    except Exception as e:
        traceback.format_exc()
        raise

def Run(args):
    args.log.info("start testing %s"%(args.shortName))
    csp_token = args.opts.cspToken
    gns = GNS(csp_token, log=args.log)
    client_cluster = os.getenv("CLUSTER") if os.getenv("CLUSTER") else args.opts.singleCluster
    assert prepare_cluster(client_cluster, log=args.log) == 0, "Failed connecting {}".format(cluster)

    gns_apis(client_cluster, gns, log=args.log)
    psv_apis(client_cluster, gns, log=args.log)
