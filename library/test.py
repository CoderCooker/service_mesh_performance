# Copyright 2020 VMware, Inc.  All rights reserved. -- VMware Confidential
# Description: test module for service mesh performance
# Disabled: True

import os
file_path = os.path.dirname(__file__)
if not file_path:
    file_pah = '.'
base_folder_path = file_path.split('library')[0]


class Test(object):

    def __init__(self, path, regex):
        self.path = path
        self.regex = regex
        self.desc = ''
        self.groups = []
        self.serial = True
        self.disabled = False
        self.timeout = 1800
        self.testedSources = []

        if path:
            # Relative path to python file from one folder above framework
            name = path.rsplit(os.path.join(os.path.sep, base_folder_path))[-1]
            name = name.lstrip(os.path.sep)
            self.name = name

            # module name from importing
            name = name.split('.')[0].replace(os.path.sep, '.')
            self.moduleName = name

            if name.find('.') != -1:
                # short name for display and  for __import__
                name = name.rsplit('.', 1)[-1]
            self.shortName = name
            self.subModuleName = name
            self.get_meta_data()

    def get_meta_data(self):
        """
        Given an absolute path to a test file, open the file and extract its
        metadata (e.g. description, type, group, etc).
        """

        with open(self.path) as f:
            for line in f:
                for metavar, regex in self.regex:
                    if regex.search(line):
                        if metavar == 'groups':
                            group_name = regex.search(
                                line).group(1).strip().lower()
                            group_type = regex.search(
                                line).group(2).strip().lower()
                            self.groups.append([group_name, group_type])
                        elif metavar == 'testedSources':
                            tested_sources = regex.search(
                                line).group(1).split(',')
                            self.testedSources = [ts.strip()
                                                  for ts in tested_sources]
                        else:
                            meta_value = regex.search(line).group(1)
                            if metavar != 'desc':
                                meta_value = meta_value.lower().strip()
                            setattr(self, metavar, meta_value)
                        break

                if not line.startswith('#'):
                    break

        assert self.desc, 'No "Description:" metadata found in %s' % self.path
        assert self.groups or self.disabled,\
            'Every test needs a "Group-*:" or "Disabled:" field: %s' % self.path
        for groupName, groupType in self.groups:
            assert groupType in ['required', 'optional', 'disabled'],\
                '"Group-%s: %s" must be "required", "optional", or "disabled" '' \
                ''in %s' % (groupName, groupType, self.path)
