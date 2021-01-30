# Copyright 2020 VMware, Inc.  All rights reserved. -- VMware Confidential
# Description: config module for service mesh performance
# Disabled: True

import os
from log import Log
from misc import display
from argparse import ArgumentParser
import time
import re
from misc import display
from test import Test

execution_path = os.path.dirname(__file__)

class Config(object):

    def __init__(self, external_test_vpx=False):
        self.logObj = None
        self.opts = self.get_options()
        self.time_label = int(time.time())
        
    def get_options(self):
        usage = """
        "" usage of the pyframework
        """
        conf_parse = ArgumentParser(add_help=False)
        conf_parse.add_argument("-c","--config_file",metavar='File',
                                default = os.path.join(execution_path, ".." + "pyframework.cfg"),
                                                       help='specify absolute path of the configuration file')
        args, remaining_args = conf_parse.parse_known_args()
        
        config_file = None
        
        parser = ArgumentParser(usage=usage, parents=[conf_parse])
        
        env_group = parser.add_argument_group("environment")
        env_group.add_argument("--log-dir", dest="logDir", metavar='DIR', 
                               help="overrides /tmp or c:\\tmp" )
        env_group.add_argument("--tests-dir",dest="testsDir", metavar='DIR',
                               help="overrides TESTSDIR environment or autodiscoverred tests dir")
        parser.add_argument_group(env_group)
        
        rt_group = parser.add_argument_group("Runtime")
        rt_group.add_argument("--debug-mode", dest='debugMode', action='store_true',
                              help="execute test case serializingly for debugging.")
        rt_group.add_argument("--csp-token", dest='cspToken', action='store',
                              help="csp refresh token for access.")
        rt_group.add_argument("--client-cluster", dest='clientCluster', action='store',
                              help="the client cluster which is test against.")
        rt_group.add_argument("--server-cluster", dest='serverCluster', action='store',
                              help="the server cluster which is test against.")
        rt_group.add_argument("--cluster", dest='singleCluster', action='store',
                              help="the single cluster which is test against.")
        rt_group.add_argument("--cluster-type", dest='clusterType', action='store',
                              help="cluster type.")
        rt_group.add_argument("--cleanup", dest='cleanUp',action='store',
                              help="cleanup the cluster resource or not")
        rt_group.add_argument("--onboard", dest='onBoard',action='store',
                              help="onboard the cluster or not")
        rt_group.add_argument("--skip-installation", dest='skipInstallation',
                              help="skip cluster installation")
        rt_group.add_argument("--clusters-per-tenant", dest='clustersNumberPerTenant',action='store',
                              help="the number of clusters deployed to a tenant")
        rt_group.add_argument("--apps-per-cluster", dest='appsPerCluster',action='store',
                              help="the number of applications deployed to a cluster")
        rt_group.add_argument("--clusters", dest='clusterLists', action='store',
                              help="the cluster list which is being executed.")                    
        rt_group.add_argument("--gns-domain", dest='gnsDomain', action='store',
                              help="the GNS domain where PODS are located.")
        rt_group.add_argument("--iteration-number", dest='iterationNumber', action='store',
                              help="the iteration number of API call.")
        rt_group.add_argument("--skip-onboard", dest='skipOnboard', action='store',
                              help="skip cluster on/off board.")
        rt_group.add_argument("--protocol-mode", dest='protocolMode', metavar='GRPC|HTTP|TCP',
        action='store', help="using which protocol loading tests.")

        rt_group.add_argument("--graph_type", dest='graphType', metavar='latency-p50, latency-p90, latency-p99, latency-p999, cpu-client, cpu-server, mem-client, mem-server',
        action='store', help="data type")
        rt_group.add_argument("--x_axis", dest='xAxis', metavar='qps or conn',
        action='store', help="xaxis type")
        rt_group.add_argument("--telemetry_modes", dest='telemetryModes', metavar='none_mtls_baseline, none_mtls_both, v2-sd-full-nullvm_both, v2-stats-nullvm_both, v2-stats-wasm_both, v2-sd-nologging-nullvm_both',
        action='store', help="This is a list of perf test labels, currently it can be any combinations from the follow supported modes")
        rt_group.add_argument("--query_list", dest='queryList', metavar='conn_query_list=[2, 4, 8, 16, 32, 64], qps_query_list=[10, 100, 200, 400, 800, 1000]',
        action='store', help="Specify the qps or conn range you want to plot based on the CSV file.")
        rt_group.add_argument("--query_str", dest='queryStr', metavar='conn_query_str=ActualQPS==1000, qps_query_str=NumThreads==16',
        action='store', help="Specify the qps or conn query_str that will be used to query your y-axis data based on the CSV file.")
        rt_group.add_argument("--csv_filepath", dest='csvFilepath', metavar='The path of the CSV file',
        action='store', help="The path of the CSV file.")
        rt_group.add_argument("--graph_title", dest='graphTitle', metavar='The graph title.',
        action='store', help="The graph title.")

        parser.add_argument_group(rt_group)
        
        opts = parser.parse_args(remaining_args)
        return opts
        
    def check_options(self, standalone=False):
        log_file = os.path.join(os.path.join(self.opts.logDir, "test-pyframe.log"))
        self.logObj = Log(filename="test-pyframe.log", log_dir=self.opts.logDir,console_output=self.opts.debugMode)
        display("logs %s"%(self.logObj.logDir))
        display("log files %s"%(os.path.join(self.logObj.logDir, "test-pyframe.log")))
    
    def all_tests(self):
        regex = [
        ['desc', re.compile(r'#\s+Description:(.+)\n$', re.IGNORECASE)],
        ['groups', re.compile(
            r'#\s+Group-([^:]+):(.+)\n$', re.IGNORECASE)],
        ['serial', re.compile(r'#\s+Serial-only:(.+)\n$', re.IGNORECASE)],
        ['disabled', re.compile(r'#\s+Disabled:(.+)\n$', re.IGNORECASE)],
        ['timeout', re.compile(r'#\s+Timeout:(.+)\n$', re.IGNORECASE)],
        ['testedSources',
            re.compile(r'#\s+Tested source files:(.+)\n$', re.IGNORECASE)]]
        tests = []
        ignore_files = ['testmypyframework.py', 'pyfra.py']
        ignore_folders = ['library']
        for path, dirs, files in os.walk(self.opts.testsDir, topdown=True):
            dirs[:] = [d for d in dirs if d not in ignore_folders]
            for filename in files:
                if filename in ignore_files:
                    continue
                if filename.endswith('.py') and filename != '__init__.py' and\
                 not re.search('^.#', filename):
                    test = Test(os.path.join(path, filename), regex)
                    tests.append(test)
        return tests
    
    def tests_to_run(self):       
        tests_to_run = []
        all_tests = self.all_tests()
        for test in all_tests:
            if test.disabled and re.search('True|Yes|1', test.disabled, re.I):
                continue
            tests_to_run.append(test)
        return tests_to_run
