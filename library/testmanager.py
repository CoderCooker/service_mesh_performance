# Copyright 2020 VMware, Inc.  All rights reserved. -- VMware Confidential
# Description: performance test manager for service mesh performance
# Disabled: True

from testprocess import TestProcess
import os
import time
from misc import display
import json
import multiprocessing
import re
import subprocess
from collections import deque

class PrintRunningTests(multiprocessing.Process):
    """Continuously print the list of running tests until there are no more."""
    def __init__(self, tests, opts):
        multiprocessing.Process.__init__(self)
        self.tests = tests
        self.opts = opts

    def run(self):
        try:
            while True:
                if self.tests and not self.opts.remoteDebugMode:
                    tests = ', '.join(sorted(self.tests))[:57].rstrip(',')\
                        .ljust(60, '.')
                    text = ' * %sRUNNING' % tests
                    display(text, new_line=False, erase_line=True)
                time.sleep(1)
        except KeyboardInterrupt:
            print

class TestManager(object):
    
    def __init__(self,cfg):
        self.cfg = cfg
        self.opts = cfg.opts
        self.log = cfg.logObj.log
        self.logDir = cfg.opts.logDir
        self.time_label = cfg.time_label
        self.testId = 0
        self.ctrlC = False
        self.retryIteration = 0
        self.results = {'PASS': [], 'FAIL': [], 'ABORT': [], 'TIMEOUT': [], 'SETUPFAIL': []}
        manager = multiprocessing.Manager()
        self.running_tests = manager.list()

    
    def run_tests(self):
        test_args = self.setup_args()
        
        parallel_tests, serial_tests = self._get_parallel_and_serial_tests()

        # Run the tests
        print_running_tests = PrintRunningTests(self.running_tests, self.opts)
        if not self.opts.debugMode:
            display('*' * 80)
            print_running_tests.start()
        start_time = int(time.time())

        self._run_parallel_tests(serial_tests, test_args)
    
        duration = int(time.time()) - start_time
        if print_running_tests.is_alive():
            print_running_tests.terminate()
        
        # display results and clean up
        self.log.debug('Calling _displayAndLogResults')
        self._display_and_log_results(duration)
        self.log.debug('Calling _WriteResultJsonFile')
        self._write_result_json_file()

    def setup_args(self):
        test_args = dict()
        test_args['opts'] = self.opts
        test_args['cfg'] = self.cfg
        return test_args
    
    def _get_parallel_and_serial_tests(self):
        parallel_tests, serial_tests = [], []
        tests_to_run = self.cfg.tests_to_run()
        for test in tests_to_run:
            if test.serial or self.opts.debugMode or self.opts.serialOnly:
                serial_tests.append(test)
            else:
                parallel_tests.append(test)

        return parallel_tests, serial_tests
    
    def _run_serial_tests(self, serial_tests, test_args):
        process = None
        for test in serial_tests:
            if self.ctrlC:
                abort_test = dict()
                abort_test['name'] = test.name
                self.results['ABORT'] += [abort_test]
                continue
            try:
                self.testId += 1
                name = test.moduleName
                test_args['name'] = name
                test_args['testId'] = self.testId
                test_args['moduleName'] = test.moduleName
                test_args['subModuleName'] = test.subModuleName
                test_args['shortName'] = test.shortName
                test_args['longName'] = test.name.replace(os.path.sep, '.')
                racetrack_failure = os.path.join(self.logDir, 'rt-fail.txt')
                if os.path.exists(racetrack_failure):
                    os.remove(racetrack_failure)

                process = TestProcess(test_args, test, self.opts, self.log, self.logDir, 
                                      self.running_tests, not self.opts.debugMode)
                process.start()
                process.join(int(process.metadata.timeout))
                if process.is_alive():
                    process.terminate()
                    self.log.debug('Test %(name)s took longer than %(sec)s.',
                                   {'name': name,
                                    'sec': process.metadata.timeout})
                    process.isTestTimedOut = True
                test_info = process.get_test_info()
                if process.isTestTimedOut:
                    self.results['TIMEOUT'] += [test_info]
                    if self.opts.stopOnError:
                        raise KeyboardInterrupt
                elif process.is_alive():
                    raise KeyboardInterrupt
                elif process.exitcode:
                    self.results['FAIL'] += [test_info]
                    if self.opts.stopOnError:
                        raise KeyboardInterrupt
                elif test_info['result']:
                    self.results[test_info['result']] += [test_info]
                else:
                    if os.path.exists(racetrack_failure):
                        self.log.error('FAIL: %s' % test.name)
                        self.results['FAIL'] += [test_info]
                        os.remove(racetrack_failure)
                    else:
                        # Successful exit with no results, assume pass
                        self.results['PASS'] += [test_info]
            except KeyboardInterrupt:
                if process.is_alive():
                    process.terminate()
                    process.join()
                    try:
                        self.results['ABORT'] += [process.get_test_info()]
                    except IOError:
                        pass

    def _display_and_log_results(self, duration):
        detailed_status = []
        for status in ['ABORT', 'FAIL', 'PASS', 'TIMEOUT']:
            if self.results[status]:
                detailed_status += ['%s (%d/%d)' % (status,
                                                    len(self.results[status]),
                                                    len(self.cfg.tests_to_run()))]
        display('\n Results: %s in %ds.' % (', '.join(detailed_status),
                                            duration))
        display('*' * 80)

        results_summary = []
        for result in ['FAIL', 'ABORT', 'PASS', 'TIMEOUT']:
            for test in self.results[result]:
                results_summary += [' * %s%s' % (test['name'].ljust(60, '.'),
                                                 result)]
        self.log.info('Results summary:\n%s' % '\n'.join(results_summary))

    def _write_result_json_file(self):
        json_filename = os.path.join(self.logDir, "results.json")
        self.log.debug('Opening file %s' % json_filename)
        f = open(json_filename, 'w')
        results = []
        for result in self.results:
            results += self.results[result]
        self.log.debug('Writing JSON results to file %s' % json_filename)
        f.write(json.dumps(results, indent=4))
        self.log.debug('Closing file %s' % json_filename)
        f.close()
        self.log.debug('File %s closed' % json_filename)

    def _run_parallel_tests(self, parallel_tests, test_args):
        test_processes = []
        running_process = deque()

        for test in parallel_tests:
            self.testId += 1
            name = test.moduleName
            test_args['name'] = name
            test_args['testId'] = self.testId
            test_args['moduleName'] = test.moduleName
            test_args['subModuleName'] = test.subModuleName
            test_args['shortName'] = test.shortName
            test_args['longName'] = test.name.replace(os.path.sep, '.')
            test_args['retry'] = self.retryIteration

            try:
                process = TestProcess(test_args, test, self.opts, self.log, self.logDir, 
                                      self.running_tests, not self.opts.debugMode)
                process.start()

                test_processes.append([process, name])
                running_process.append([process, name])
            except KeyboardInterrupt:
                self.ctrlC = True
                break

        try:
            if self.ctrlC:
                raise KeyboardInterrupt
            else:
                # Keep track of test process.  If the process hasn't started
                # running the test, put it back to the queue. If it has started
                # running the test, wait for timeout (test metadata timeout +
                # timeout for cleaning up after running the test), terminate the
                # process forcefully if the test doesn't finish on time/stuck
                # while cleaning up.

                while len(running_process) != 0:
                    process, name = running_process.popleft()
                    if process.is_alive():
                        if process.is_running() == 1:
                            metadata_timeout = int(process.metadata.timeout)
                            process.join(metadata_timeout)
                            if process.is_alive():
                                # forcefully terminate the process, if it hasn't
                                # exited after timeout
                                process.terminate()
                                process.join()
                                self.log.debug(
                                    'Test %(name)s took longer than ' +
                                    '%(sec)d, Terminating forcefully now',
                                    {'name': name, 'sec': metadata_timeout})
                                process.isTestTimedOut = True
                            if process.exitcode and self.opts.stopOnError:
                                raise KeyboardInterrupt
                        else:
                            # if test process hasn't actually started running
                            # the test, put it back in the queue
                            running_process.append([process, name])
        except KeyboardInterrupt:
            self.ctrlC = True

        for process, name in test_processes:
            test_info = process.get_test_info()
            if process.isTestTimedOut:
                self.results['TIMEOUT'] += [test_info]
            elif process.is_alive():
                process.terminate()
                process.join()
                self.results['ABORT'] += [test_info]
            elif process.exitcode:
                self.results['FAIL'] += [test_info]
            elif test_info['result']:
                self.results[test_info['result']] += [test_info]
            else:
                # Successful exit with no results, assume pass
                self.results['PASS'] += [test_info]
