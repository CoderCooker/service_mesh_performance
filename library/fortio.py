# Copyright Istio Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import print_function
import json
import os
import shlex
import requests
from datetime import datetime
import calendar
import csv
import argparse
import subprocess
import tempfile
import prom
from subprocess import getoutput
from constants import *
from kubenertes_utils import *
from utils import *
import traceback
import random

"""
    returns data in a single line format
    Labels, StartTime, RequestedQPS, ActualQPS, NumThreads,
    min, max, p50, p75, p90, p99, p999
"""

NAMESPACE = os.environ.get("NAMESPACE", "fortioclient")

def generate_tests_results(client_cluster, log=None):
    try:
        context = "{}/{}".format(AWS_EKS_DESC, client_cluster)
        fortioclient_loadbalancer = get_service_loadbalancer(context, FORTIO_CLIENT_NAMESPACE, FORTIO_CLIENT_SERVICE, log=log)
        FORTIO_CLIENT_URL = "http://{}:{}".format(fortioclient_loadbalancer, FORTIO_CLIENT_PORT)

        istio_loadbalancer = get_service_loadbalancer(context, ISTIO_NAMESPACE, ISTIO_INGRESSGATEWAY, log=log)
        PROMETHEUS_URL = "http://{}:{}".format(istio_loadbalancer, EKS_LOADBALANCER_PORT)
        table = None

        print("FORTIO_CLIENT_URL {} -- PROMETHEUS_URL {} -- namespace {} -- context {}".format(FORTIO_CLIENT_URL, PROMETHEUS_URL, FORTIO_CLIENT_NAMESPACE, context))
        file_path = "/var/lib/jenkins/workspace/%s" % (os.getenv("JOB_NAME"))
        random_name = ''.join(random.choices(string.ascii_lowercase + string.digits, k = 10))
        csv_output = "{}/{}.csv".format(file_path,random_name)
        random_name = ''.join(random.choices(string.ascii_lowercase + string.digits, k = 10))
        json_output = "{}/{}.json".format(file_path,random_name)
        sync_fortio(FORTIO_CLIENT_URL, table, promUrl=PROMETHEUS_URL, csv=FORTIO_RES_SUFFIX, namespace=FORTIO_CLIENT_NAMESPACE, context=context,
                                json_output=json_output, csv_output=csv_output)
        return json_output, csv_output
    except Exception as e:
        traceback.format_exc()
        raise

def load_tests_cmd(cluster, pod_name, gns_domain, uid, conn=2, qps=1000, duration=240, proto="HTTP", log=None):
    tests_cmd = ""
    if proto.upper() == "GRPC":
        label = "grpc_{}_qps_{}_c_{}_1024_v2-stats-nullvm_both".format(uid, qps, conn)
        tests_cmd = "kubectl --context {}/{} -n fortioclient"\
                    " exec {}"\
                    " -- fortio load -jitter=False -grpc -ping -a -httpbufferkb=128 -c {} -qps {} -t {}s"\
                    " -labels {} http://fortioserver.{}:{}".format(AWS_EKS_DESC, cluster,
                    pod_name, conn, qps, duration, label, gns_domain, FORTIO_SERVER_GRPC_PORT)
    elif proto.upper() == "HTTP":
        label = "http_{}_qps_{}_c_{}_1024_v2-stats-nullvm_both".format(uid, qps, conn)
        tests_cmd = "kubectl --context {}/{} -n fortioclient"\
                        " exec {}"\
                        " -- fortio load -jitter=False -a -httpbufferkb=128 -c {} -qps {} -t {}s "\
                        " -labels {} http://fortioserver.{}:{}".format(AWS_EKS_DESC, cluster,
                        pod_name, conn, qps, duration, label, gns_domain, FORTIO_SERVER_HTTP_PORT)
    elif proto.upper() == "TCP":
        label = "tcp_{}_qps_{}_c_{}_1024_v2-stats-nullvm_both".format(uid, qps, conn)
        tests_cmd = "kubectl --context {}/{} -n fortioclient"\
                  " exec {}"\
                  " -- fortio load  -jitter=False -a -httpbufferkb=128 -c {} -qps {} -t {}s "\
                  " -labels {} tcp://fortioserver.{}:{}".format(AWS_EKS_DESC, cluster, 
                  pod_name, conn, qps, duration, label, gns_domain, FORTIO_SERVER_TCP_PORT)
    else:
        raise Exception("unsupported fortio protocol {}".format(proto))

    if log:
        log.info("loading tests --- {}".format(tests_cmd))

    rt, out, err = run_local_sh_cmd(tests_cmd)
    if rt != 0:
        raise Exception("failed running tests rt {} out {} err {}".format(rt, out, err))
    return 0

def convert_data(data):
    obj = {}

    # These keys are generated from fortio default json file
    for key in "Labels,StartTime,RequestedQPS,ActualQPS,NumThreads,RunType,ActualDuration".split(
            ","):
        if key == "RequestedQPS" and data[key] == "max":
            obj[key] = 99999999
            continue
        if key in ["RequestedQPS", "ActualQPS"]:
            obj[key] = int(round(float(data[key])))
            continue
        if key == "ActualDuration":
            obj[key] = int(data[key] / 10 ** 9)
            continue
        # fill out other data key to obj key
        obj[key] = data[key]

    h = data["DurationHistogram"]
    obj["min"] = int(h["Min"] * 10 ** 6)
    obj["max"] = int(h["Max"] * 10 ** 6)

    p = h["Percentiles"]

    for pp in p:
        obj["p" + str(pp["Percentile"]).replace(".", "")
            ] = int(pp["Value"] * 10 ** 6)

    success = 0
    if '200' in data["RetCodes"]:
        success = int(data["RetCodes"]["200"])

    # "Sizes" key is not in RunType: TCP
    if data["RunType"] == "HTTP":
        obj["errorPercent"] = 100 * \
            (int(data["Sizes"]["Count"]) - success) / int(data["Sizes"]["Count"])
        obj["Payload"] = int(data['Sizes']['Avg'])
    return obj


def fetch(url):
    data = None
    if url.startswith("http"):
        try:
            d = requests.get(url)
            if d.status_code != 200:
                return None
            # Add debugging info for JSON parsing error in perf pipeline (nighthawk)
            print("fetching data from fortioclient")
            print(d)
            data = d.json()
        except Exception:
            print("Error while fetching from " + url)
            raise
    else:
        data = json.load(open(url))

    return convert_data(data)


def convert_data_to_list(txt):
    idx = 0
    lines = []

    marker = '<option value="'
    # marker = 'a href="' # This used to be the marker in older version of
    # fortio
    while True:
        idx = txt.find(marker, idx)
        if idx == -1:
            break
        startRef = idx + len(marker)
        end = txt.find('"', startRef)
        lines.append(txt[startRef:end])
        idx += 1
    return lines


# number of seconds to skip after test begins.
METRICS_START_SKIP_DURATION = 62
# number of seconds to skip before test ends.
METRICS_END_SKIP_DURATION = 30
# number of seconds to summarize during test
METRICS_SUMMARY_DURATION = 180

def sync_fortio(url, table, selector=None, promUrl="", csv=None, json_output="", csv_output="", namespace=None, context=None):
    get_fortioclient_pod_cmd = "kubectl -n {namespace} get pods | grep fortioclient".format(namespace=namespace)
    if context:
        get_fortioclient_pod_cmd = "kubectl --context {context} -n {namespace} get pods | grep fortioclient".format(context=context, namespace=namespace)
    print("get_fortioclient_pod_cmd {}".format(get_fortioclient_pod_cmd))
    
    fortioclient_pod_name = getoutput(get_fortioclient_pod_cmd).split(" ")[0]
    print("fortioclient_pod_name {}".format(fortioclient_pod_name))

    temp_dir_path = tempfile.gettempdir() + "/fortio_json_data"
    get_fortio_json_cmd = "kubectl cp -c shell {namespace}/{fortioclient}:/var/lib/fortio {tempdir}"\
        .format(namespace=namespace, fortioclient=fortioclient_pod_name, tempdir=temp_dir_path)
    if context:
        get_fortio_json_cmd = "kubectl --context {context} cp -c shell {namespace}/{fortioclient}:/var/lib/fortio {tempdir}"\
        .format(context=context, namespace=namespace, fortioclient=fortioclient_pod_name, tempdir=temp_dir_path)
    print("get_fortio_json_cmd {}".format(get_fortio_json_cmd))
    rt, out, err = run_local_sh_cmd(get_fortio_json_cmd)
    if rt != 0:
        msg = "failed executing {}, err {}".format(get_fortio_json_cmd, err)
        raise Exception(msg)

    datafile = json_output
    fd = os.open(datafile, os.O_RDWR|os.O_CREAT)
    out = os.fdopen(fd, "wt")
    stats = []
    cnt = 0

    data = []
    for filename in os.listdir(temp_dir_path):
        print("filename -- " + filename)
        with open(os.path.join(temp_dir_path, filename), 'r') as f:
            try:
                data_dict = json.load(f, strict=False)
                one_char = f.read(1)
                if not one_char:
                    print("json file is not empty")
            except json.JSONDecodeError as e:
                print(f.read())
                while True:
                    line = f.readline()
                    print(line)
                    if "" == line:
                        print("file finished!")
                        break
                print(e)

            gd = convert_data(data_dict)
            if gd is None:
                print("gd is none")
                continue
            st = gd['StartTime']
            if selector is not None:
                if selector.startswith("^"):
                    if not st.startswith(selector[1:]):
                        continue
                elif selector not in gd["Labels"]:
                    continue

            if promUrl:
                print("prmUrl -- {}".format(promUrl))
                sd = datetime.strptime(st[:19], "%Y-%m-%dT%H:%M:%S")
                print("Fetching prometheus metrics for", sd, gd["Labels"])
                # if data["RunType"] == "HTTP":
                #     if gd['errorPercent'] > 10:
                #         print("... Run resulted in", gd['errorPercent'], "% errors")
                #         continue
                min_duration = METRICS_START_SKIP_DURATION + METRICS_END_SKIP_DURATION
                if min_duration > gd['ActualDuration']:
                    print("remove me duration duration")
                    print("... {} duration={}s is less than minimum {}s".format(
                        gd["Labels"], gd['ActualDuration'], min_duration))
                    continue
                prom_start = calendar.timegm(
                    sd.utctimetuple()) + METRICS_START_SKIP_DURATION
                duration = min(gd['ActualDuration'] - min_duration,
                               METRICS_SUMMARY_DURATION)
                p = prom.Prom(promUrl, duration, start=prom_start)
                prom_metrics = p.fetch_istio_proxy_cpu_and_mem()
                if not prom_metrics:
                    print("... Not found")
                    continue
                else:
                    print("else -- ")
                    print("")

                gd.update(prom_metrics)

            data.append(gd)
            print("gd dump data -- {}".format(json.dumps(gd)))
            out.write(json.dumps(gd) + "\n")
            stats.append(gd)
            cnt += 1

    out.close()
    print("Wrote {} json records to {}".format(cnt, datafile))

    if csv is not None:
        write_csv(csv, data, csv_output)

    if table:
        return write_table(table, datafile)

    print("\n sync_fortio end json result {} csv result {}".format(datafile, csv_output))
    return 0

def write_csv(keys, data, csv_output):
    if csv_output is None or csv_output == "":
        fd, csv_output = tempfile.mkstemp(suffix=".csv")
        out = os.fdopen(fd, "wt")
    else:
        out = open(csv_output, "w+")

    lst = keys.split(',')
    out.write(keys + "\n")

    for gd in data:
        row = []
        for key in lst:
            row.append(str(gd.get(key, '-')))

        out.write(','.join(row) + "\n")

    out.close()
    print("Wrote {} csv records to {}".format(len(data), csv_output))
    return 0


def write_table(table, datafile):
    print("table: %s, datafile: %s" % (table, datafile))
    p = subprocess.Popen("bq insert {table} {datafile}".format(
        table=table, datafile=datafile).split())
    ret = p.wait()
    print(p.stdout)
    print(p.stderr)
    return ret

def get_parser():
    parser = argparse.ArgumentParser("Fetch and upload results to bigQuery")
    parser.add_argument(
        "--table",
        help="Name of the BigQuery table to send results to, like istio_perf_01.perf",
        default=None)
    parser.add_argument(
        "--selector",
        help="timestamps to match for import")
    parser.add_argument(
        "--csv",
        help="columns in the csv file",
        default="StartTime,ActualDuration,Labels,NumThreads,ActualQPS,p50,p90,p99,p999"
                "cpu_mili_avg_istio_proxy_fortioclient,cpu_mili_avg_istio_proxy_fortioserver,"
                "cpu_mili_avg_istio_proxy_istio-ingressgateway,mem_Mi_avg_istio_proxy_fortioclient,"
                "mem_Mi_avg_istio_proxy_fortioserver,mem_Mi_avg_istio_proxy_istio-ingressgateway")
    parser.add_argument(
        "--csv_output",
        help="output path of csv file")
    parser.add_argument(
        "url",
        help="url to fetch fortio json results from")
    parser.add_argument(
        "--prometheus",
        help="url to fetch prometheus results from. if blank, will only output Fortio metrics.",
        default="")
    parser.add_argument(
        "--namespace",
        help="namespace that tests are issued.",
        default="")
    parser.add_argument(
        "--context",
        help="context that tests are executed.",
        default="")
    return parser
