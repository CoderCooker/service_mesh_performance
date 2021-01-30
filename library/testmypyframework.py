# Copyright 2020 VMware, Inc.  All rights reserved. -- VMware Confidential
# Description: test root module for service mesh performance
# Disabled: True

import traceback
from config import Config
import sys

def main():
    config = None
    try:
        config = Config()
        config.check_options()
        from testmanager import TestManager
        test_manager = TestManager(config)
        test_manager.cfg.logObj.log.debug(sys.argv)
        temp_argv = ''
        for argv in sys.argv:
            temp_argv += argv + ' '
        test_manager.cfg.logObj.log.debug(temp_argv)
        test_manager.run_tests()
    except Exception as e:
        print(traceback.format_exc())
        