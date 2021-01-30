# Copyright 2020 VMware, Inc.  All rights reserved. -- VMware Confidential
# Description: misc utility for service mesh performance
# Disabled: True

import sys

def display(msg, new_line=True, erase_line=True):
    if erase_line:
        msg = '\r%s' % msg
    if new_line:
        print(msg)
    elif sys.stdout.isatty():
        sys.stdout.write(msg)
        sys.stdout.flush()
    
if __name__ == '__main__':
    pass