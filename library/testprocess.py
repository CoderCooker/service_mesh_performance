# Copyright 2020 VMware, Inc.  All rights reserved. -- VMware Confidential
# Description: testprocess module for service mesh performance
# Disabled: True

import os
from log import Log
import traceback
import sys
import os.path
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
import importlib
import multiprocessing
import time
from misc import display

class RunArgs(object):
    def __init__(self, **kwargs):
        for attr in kwargs.keys():
            setattr(self, attr, kwargs[attr])
        
class TestProcess(multiprocessing.Process):
    
    def __init__(self, test_args, metadata, opts, log_obj_from_manager, log_dir_from_manager,
                 running_tests,
                 process=False):
        multiprocessing.Process.__init__(self)
        self.test_args = test_args
        self.name = test_args['name']
        self.metadata = metadata
        self.longName = self.test_args['longName']
        self.modulename = self.test_args['moduleName']
        self.submodulename = self.test_args['subModuleName']
        self.testBegin = multiprocessing.Value('i', 0)
        self.log_obj = log_obj_from_manager
        self.logDir = log_dir_from_manager
        self.isTestTimedOut = False
        self.testInfo = multiprocessing.Manager().dict()
        self.testInfo['name'] = self.name
        self.testInfo['duration'] = None
        self.testInfo['logPath'] = None
        self.testInfo['result'] = None
        self.testInfo['startTime'] = None
        self.opts = opts
        self.running_tests = running_tests
        self.process = process
    
    def get_test_info(self):
        return self.testInfo.copy()

    def run(self):
        args = None
        name = self.metadata.moduleName
        short_name = self.metadata.shortName
        log_name = "test-pyframe.{0}.log".format(name)
        log_path = os.path.join(self.logDir, log_name)
        log_obj = self.log_obj
        log = self.test_args['log'] = self.log_obj
        self.test_args['logDir'] = self.logDir
        self.testInfo['logPath'] = log_path
        
        module = None
        try:
            log.debug('Importing %(module)s...', {'module': name})
            module = importlib.import_module(name)
        except (SyntaxError, ImportError) as e:
            log.error(traceback.format_exc())
            log.error("Error import modules %(e)s", {'e': e})
            result = 'SETUPFAIL'
            self.testInfo['result'] = result
            return
        
        if 'Run' not in dir(module):
            log.error("Run method is not defined in the ")

        args = None
        duration = None
        try:
            # self.test_args['extra_test_args'] = self.opts.extra_test_args
            log.info('Starting test %s...' % name)
            self.testInfo['startTime'] = time.strftime(
                    "%a, %d %b %Y %H:%M:%S",
                    time.localtime())
            start_time = int(time.time())

            self.running_tests.append(short_name)
            # self.testBegin.value = 1

            args = RunArgs(**self.test_args)
            result = module.Run(args)
            duration = int(time.time()) - start_time
        except Exception as e:
            result = 'FAIL'
            log.exception('Test exception: %(e)s', {'e': e})
            log.error(traceback.format_exc())
        except AssertionError as error:
            result = 'FAIL'
            log.error(error)
        
        # Print results
        result = 'PASS' if not result else result.upper()
        result_line = ' * %s%s (%ss)' % (name.ljust(60, '.'), result, duration)
        display(result_line, erase_line=True)
        if result.endswith('FAIL'):
            display('   log: %s' % log_path)
        log.info(result_line)

        self.testInfo['duration'] = duration
        self.testInfo['result'] = result

        # Upon failure, notify the parent process with a return code
        log.debug('Cleaning up done for test:%s' % self.name)

        if result != 'PASS':
            if self.process:
                sys.exit(1)
            else:
                return 1
        return 0
    
    def is_running(self):
        return self.testBegin.value