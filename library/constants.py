# Copyright 2020 VMware, Inc.  All rights reserved. -- VMware Confidential
# Description: utility module for service mesh performance
# Disabled: True

#STAGING0_API_ENDPOINT = "https://staging-0.servicemesh.biz/tsm/v1alpha1"
STAGING0_API_ENDPOINT = "https://staging-2.servicemesh.biz/tsm/v1alpha1"
STAGING_CSP_URL = "https://console-stg.cloud.vmware.com"

AWS_EKS_DESC = "arn:aws:eks:us-west-2:284299419820:cluster"

FORTIO_CLIENT_NAMESPACE = "fortioclient"
FORTIO_CLIENT_SERVICE = "fortioclient"
FORTIO_CLIENT_DEPLOYMENT = "fortioclient"
FORTIO_SERVER_NAMESPACE = "fortioserver"
FORTIO_CLIENT_PORT = 8080
FORTIO_SERVER_GRPC_PORT = 8076
FORTIO_SERVER_HTTP_PORT = 8080
FORTIO_SERVER_TCP_PORT = 8078
FORTIO_RES_SUFFIX = "--csv "\
                    "StartTime,ActualDuration,Labels,NumThreads,ActualQPS,p50,p90,p99,cpu_mili_avg_telemetry_mixer,cpu_mili_max_telemetry_mixer,"\
                    "mem_MB_max_telemetry_mixer,cpu_mili_avg_fortioserver_deployment_proxy,cpu_mili_max_fortioserver_deployment_proxy,"\
                    "mem_MB_max_fortioserver_deployment_proxy,cpu_mili_avg_ingressgateway_proxy,"\
                    "cpu_mili_max_ingressgateway_proxy,mem_MB_max_ingressgateway_proxy"

PROMETHEUS_NAMESAPCE = "monitoring"
PROMETHEUS_PORT = 9090
PROMETHEUS_SERVICE = "prometheus-service"

ISTIO_NAMESPACE = "istio-system"
ISTIO_INGRESSGATEWAY = "istio-ingressgateway"
EKS_LOADBALANCER_PORT = 80

GNS_CC_DOMAIN = "gns-2ns-cc.local"
GNS_CC_CLIENT_YAML = "https://raw.githubusercontent.com/CoderCooker/TSM-GNS-APP-Perf/main/manifests/two_clusters/fortio_test_client.yaml"
GNS_CC_SERVER_YAML = "https://raw.githubusercontent.com/CoderCooker/TSM-GNS-APP-Perf/main/manifests/two_clusters/fortio_test_server.yaml"

GNS_SC_DOMAIN = "gns-2ns-sc.local"
GNS_SC_CLIENT_YAML = "https://raw.githubusercontent.com/CoderCooker/TSM-GNS-APP-Perf/main/manifests/single_cluster/fortio_test_client.yaml"
GNS_SC_SERVER_YAML = "https://raw.githubusercontent.com/CoderCooker/TSM-GNS-APP-Perf/main/manifests/single_cluster/fortio_test_server.yaml"


NodeMetricTypes = [
    "CPUCapacity",
    "CPUUsage",
    "DiskCapacity",
    "DiskUsages",
    "DiskIO",
    "DiskWait",
    "MemoryCapacity",
    "MemoryUsages",
    "MemoryUsagesBytes",
    "IOWait",
    "NetworkIO",
    "ServiceCount",
    "ServiceInstanceCount"
]


ServiceMetricTypes =  [
    "RequestPS",
    "Requests",
    "Latency",
    "p50Latency",
    "p90Latency",
    "p99Latency",
    "ErrorRate",
    "ErrorPS",
    "ClusterCount",
    "NodeCount",
    "ServiceCount",
    "ServiceInstanceCount",
    "Response2xx",
    "Response3xx",
    "Response4xx",
    "Response5xx",
    "SuccessRate",
    "CPUUsageMillicores",
    "MemoryUsageBytes",
    "RequestResponse"
]

AGENT_NS = 'vmware-system-tsm'
DEFAULT_PERIOD = 3

SCALE_UP_APP_YAML = 'https://raw.githubusercontent.com/istio/istio/release-1.8/samples/bookinfo/platform/kube/bookinfo.yaml'
MORE_PODS_YAML = 'https://raw.githubusercontent.com/CoderCooker/vs-app/master/tsm-scale/acme-all-manifest.yaml'

KUBERNETES_ISTIO_NETWORK_GROUP = "networking.istio.io"
KUBERNETES_ISTIO_NETWORK_VERSION = "v1beta1"
KUBERNETES_ISTIO_GATEWAY_PLURAL = "gateways"

KUBERNETES_ISTIO_VIRTUAL_SERVICE_PLURALS = "virtualservices"

CLIENT_CLUSTER_PREFIX = 'span-client-clusters'
JENKINS_KUBECTL_PREFIX = "echo \'centos\' | sudo -S "

# GNS_VERIFICATION_CLS1_YAMLS=[
# "https://raw.githubusercontent.com/CoderCooker/TSM-GNS-APP-Perf/main/exhaust_gns/ACME/two_clusters/acme_fitness_cls1.yaml",
# "https://raw.githubusercontent.com/CoderCooker/TSM-GNS-APP-Perf/main/exhaust_gns/ACME/two_clusters/cls1_secrets.yaml",
# "https://raw.githubusercontent.com/CoderCooker/TSM-GNS-APP-Perf/main/exhaust_gns/ACME/two_clusters/loadgen.yaml"]

GNS_VERIFICATION_CLS1_YAMLS=[
    "https://raw.githubusercontent.com/CoderCooker/service_mesh_performance/main/setup/manifests/twoclusters/cls1.yaml",
    "https://raw.githubusercontent.com/CoderCooker/service_mesh_performance/main/setup/manifests/twoclusters/cls1-sleep.yaml"
]

# GNS_VERIFICATION_CLS2_YAMLS=[
# "https://raw.githubusercontent.com/CoderCooker/TSM-GNS-APP-Perf/main/exhaust_gns/ACME/two_clusters/acme_fitness_cls2.yaml",
# "https://raw.githubusercontent.com/CoderCooker/TSM-GNS-APP-Perf/main/exhaust_gns/ACME/two_clusters/cls2_secrets.yaml"]

GNS_VERIFICATION_CLS2_YAMLS=[
    "https://raw.githubusercontent.com/CoderCooker/service_mesh_performance/main/setup/manifests/twoclusters/cls2.yaml"
]
