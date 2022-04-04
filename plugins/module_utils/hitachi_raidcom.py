#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2021 Hitachi Vantara, Inc. All rights reserved.
# Author: Giacomo Chiapparini <@gchiapparini-hv>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)


from __future__ import absolute_import, division, print_function
__metaclass__ = type

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.hitachi.raidcom.plugins.module_utils.hitachi_raidcom_utility import raidcom

try:
    import json
except ImportError:
    import simplejson as json

try:
    from ansible.module_utils.ansible_release import __version__ as ansible_version
except ImportError:
    ansible_version = 'unknown'

import os
import ssl
import time


hitachi_raidcom_argument_spec = {
    "storage_serial": {"required": False, "type": "int"},
    "horcm_inst": {"required": True, "type": "int"},
}


class hitachi_raidcom(object):
    def __init__(self, module):
        # base init
        self.module = module
        self.params = module.params
        # result that is returned
        self.result = dict(changed=False)
        # Print Level
        self.print_debug_message = False
        # horcm_inst
        self.horcm_inst = self.params['horcm_inst']
        self.serial = self.params['storage_serial']
        self.mystorage = raidcom(self.serial, self.horcm_inst)
    # End of utils __init__

    # ####
    # # UTILITIES
    # ####

    def blkstomb(self, blks):
        MB = int(blks) / 2048
        GB = MB / 1024
        TB = GB / 1024
        PB = TB / 1024
        return {'blks': blks, 'MB': round(MB), 'GB': round(GB, 2), 'TB': round(TB, 2), 'PB': round(PB, 2)}

    def caps(self, capacity, denominator):

        if denominator == "GB":
            GB = capacity
            MB = GB * 1024
            TB = GB / 1024
            PB = TB / 1024
            blks = MB * 2048
        if denominator == "MB":
            MB = capacity
            GB = MB / 1024
            TB = GB / 1024
            PB = TB / 1024
            blks = MB * 2048
        if denominator == "blks":
            blks = capacity
            MB = int(blks) / 2048
            GB = MB / 1024
            TB = GB / 1024
            PB = TB / 1024
        if denominator == "TB":
            TB = capacity
            PB = TB / 1024
            GB = TB * 1024
            MB = GB * 1024
            blks = MB * 2048
        if denominator == "PB":
            PB = capacity
            TB = PB * 1024
            GB = TB * 1024
            MB = GB * 1024
            blks = MB * 2048

        return {'blks': round(blks), 'MB': round(MB), 'GB': round(GB, 2), 'TB': round(TB, 2), 'PB': round(PB, 2)}

    def convertSizeToBlocks(self, size):
        if not size:
            return None
        units = [
            ('PB', 2 ** 50),
            ('TB', 2 ** 40),
            ('GB', 2 ** 30),
            ('MB', 2 ** 20),
            ('KB', 2 ** 10),
            ('B', 1)]
        size = size.upper()
        for suffix, multiplier in units:
            if size.endswith(suffix):
                num_units = size[:-len(suffix)]
                try:
                    return int(float(num_units) * multiplier / 512)
                except ValueError as e:
                    self.module.fail_json(msg=' check given volumeSize (ex. 1GB) - convertSizeToBlocks Error: %s' % e)
        return None

    # #####
    # # Storage System Management
    # #####

    def volume_get_properties(self):
        result = {}
        if self.params['volume_id'] == '':
            self.params['volume_id'] = self.volume_name_to_volume_id()
        result['result'] = self.mystorage.getldev(ldevid=self.params['volume_id'])
        return result

    def volume_name_to_volume_id(self):
        if self.params['volume_name'] != '':
            result = {}
            result = self.mystorage.getldevlist(ldevtype='defined')
            # self.module.warn('{}'.format(result))
            for item in result['stdout']:
                if item.keys('LDEV_NAMING') == self.params['volume_name']:
                    volumeproperties = item
            # volumeproperties = result['stdout'].keys()[result['stdout'].values().index(self.params['volume_name'])]
            # volumeproperties = {}
            if len(volumeproperties) == 0:
                self.module.warn(msg='volume_name_to_volume_id error - volume_name is NOT found on storage.')
            else:
                return volumeproperties['LDEV']
        else:
            self.module.fail_json(msg='volume_name_to_volume_id error - volume_name is needed')

    def volume_exists(self):
        result = {}
        if self.params['volume_id'] == '':
            self.params['volume_id'] = self.volume_name_to_volume_id()
            if self.params['volume_id'] == '':
                self.module.fail_json(msg='volume_name and volume_id error - volume_name is NOT found on storage')
        result['result'] = self.mystorage.getldev(ldevid=self.params['volume_id'])
        if result['result']['stdout']['VOL_TYPE'] == "NOT DEFINED":
            return False
        else:
            return True

    def volume_get_size(self):  # (in blocks)
        if self.params['volume_id'] == '':
            self.params['volume_id'] = self.volume_name_to_volume_id()
            if self.params['volume_id'] == '':
                self.module.fail_json(msg='volume_name and volume_id error - volume_name is NOT found on storage')
        result = {}
        result['result'] = self.mystorage.getldev(ldevid=self.params['volume_id'])
        volume_getsize = result['result']['stdout']['VOL_Capacity(BLK)']
        return volume_getsize

    def volume_expand(self):
        if self.params['volume_id'] == '':
            self.params['volume_id'] = self.volume_name_to_volume_id()
            if self.params['volume_id'] == '':
                self.module.fail_json(msg='volume_name and volume_id error - volume_name is NOT found on storage')
        expand = self.mystorage.extendvolume(ldevid=self.params['volume_id'], capacityblk=self.params['volume_size'])
        return expand

    def volume_create(self):
        if self.params['volume_id'] == '':
            # use the next free ldev_id
            self.params['volume_id'] = self.mystorage.getnextfreeldev()['ldev']
        create = self.mystorage.addldev(ldevid=self.params['volume_id'], poolid=self.params['pool_id'], capacityblk=self.params['volume_size'])
        if not self.params['volume_name'] == "":
            modify_ldevname = self.mystorage.modifyldevname(ldevid=self.params['volume_id'], ldev_name=self.params['volume_name'])
        return create

    def volume_delete(self):
        if self.params['volume_id'] == '':
            self.params['volume_id'] = self.volume_name_to_volume_id()
            if self.params['volume_id'] == '':
                self.module.fail_json(msg='volume_name and volume_id error - volume_name is NOT found on storage')
        delete = self.mystorage.deletevolume(ldevid=self.params['volume_id'])
        return delete

