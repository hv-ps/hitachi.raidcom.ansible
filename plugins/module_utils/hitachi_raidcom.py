#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2021 Hitachi Vantara, Inc. All rights reserved.
# Author: Giacomo Chiapparini <@gchiapparini-hv>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)


from __future__ import absolute_import, division, print_function
__metaclass__ = type

from ansible.module_utils.basic import AnsibleModule
from hiraid.raidcom import Raidcom
from hiraid.horcm.horcm_cci import Cci
from hiraid.storage_utils import StorageCapacity

import logging

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


def createdir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

# hiraid logger configuration setup
def configlog(scriptname, logdir, logname, basedir=os.getcwd()):
    try:
        separator = ('/', '\\')[os.name == 'nt']
        cwd = basedir
        createdir('{}{}{}'.format(cwd, separator, logdir))
        logfile = '{}{}{}{}{}'.format(
            cwd, separator, logdir, separator, logname)
        logger = logging.getLogger(scriptname)
        logger.setLevel(logging.DEBUG)
        fh = logging.FileHandler(logfile)
        fh.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s : %(name)s : %(levelname)s : %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        # Add handlers to the logger
        logger.addHandler(fh)
        logger.addHandler(ch)
    except Exception as e:
        raise Exception('Unable to configure logger > {}'.format(str(e)))
    return logger


class hitachi_raidcom(object):
    def __init__(self, module):
        # enable hiraid logging
        self.log = configlog("hitachi_raidcom_module_utils", "", "hitachi_raidcom_collection.log",basedir="/var/log")
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
        # Darren
        # self.mystorage = raidcom(self.serial, self.horcm_inst)
        self.mystorage = Raidcom(self.serial, self.horcm_inst,log=self.log)
        # add cci commands to storage
        self.mystorage.cci = Cci(log=self.log)
    # End of utils __init__

    # ####
    # # UTILITIES to be moved into hiraid
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
                    self.module.fail_json(
                        msg=' check given volumeSize (ex. 1GB) - convertSizeToBlocks Error: %s' % e)
        return None

    # #####
    # # Storage System Management
    # #####

    def volume_get_properties(self):
        result = {}
        # self.module.fail_json(msg='{}'.format(self.params['volume_id']))
        if self.params['volume_id'] == "":
            self.params['volume_id'] = self.volume_name_to_volume_id()
        # if volume ID is still "" we did not found any volume with given name
        if self.params['volume_id'] == "":
            # not found
            result['result'] = {"no volume with this volume_name found"}
        else:
            result['result'] = self.mystorage.getldev(
                ldev_id=self.params['volume_id']).view
        return result

    def volume_name_to_volume_id(self):
        if self.params['volume_name'] != '':
            result = {}
            # result to give back
            resultVolumeId = ""
            # as volume_name is not enforced to be unique in storage
            # we need to verify it realy only exists once
            # once Hitachi storage can enforce single volume_name this routine can be simplified
            countOfNameOccuranceInStorage = 0
            # get all LDEVS including it's volume_names
            result = self.mystorage.getldevlist(ldevtype='defined').view
            for item in result:
                if result[item]['LDEV_NAMING'] == self.params['volume_name']:
                    countOfNameOccuranceInStorage = countOfNameOccuranceInStorage + 1
                    resultVolumeId = result[item]['LDEV']
                    # self.module.fail_json(msg='volume_name_to_volume_id - Found: {} '.format(result[item]['LDEV']))
                    # return resultVolumeId
            if countOfNameOccuranceInStorage == 0:
                # volume_name does not yet exists
                return ""
            if countOfNameOccuranceInStorage == 1:
                # one volume with this name found
                # check if found LDEVID is equeal given LDEVID, if one given
                if self.params['volume_id'] != '':
                    # given LDEVID
                    if self.params['volume_id'] != resultVolumeId:
                        # there is a volume with the same label but different volume id,
                        # we can not change ldev id
                        # fail
                        self.module.fail_json(msg='volume_name_to_volume_id error - volume_name found on storage but for a different volume_id. Please correct your entries. current:{} given:{}'.format(
                            resultVolumeId, self.params['volume_id']))

                return resultVolumeId
            # in all other cases we have an error
            self.module.fail_json(
                msg='volume_name_to_volume_id error - volume_name is not unique. Found {} volumes with same name.'.format(str(countOfNameOccuranceInStorage)))
        else:
            if self.params['volume_id'] != '':
                # return given volume_id
                return self.params['volume_id']
            else:
                # fail as we do not have volume_name and not volume_id
                self.module.fail_json(
                    msg='volume_name_to_volume_id error - volume_name is needed')

    def volume_exists(self):
        result = {}
        if self.params['volume_id'] == '':
            if self.params['volume_name'] == '':
                # fail: we either need volume_id or volume_name
                self.module.fail_json(
                    msg='volume_name and volume_id error - either volume_name or volume_id is needed')
            else:
                # search for volume_name to get volume_id
                self.params['volume_id'] = self.volume_name_to_volume_id()
                if self.params['volume_id'] == '':
                    # volume_name not found on storage
                    return False
                else:
                    # volume_id found (please not that volume_name_to_volume_id makes sure exactly one is defined on storage, or fails)
                    return True
        else:
            # a volume_name is given but no volume_id - default behaviour in Ansible
            # get volume_id's properties
            result['result'] = self.mystorage.getldev(
                ldev_id=self.params['volume_id']).view
            if result['result'][str(self.params['volume_id'])]['VOL_TYPE'] == "NOT DEFINED":
                # volume_id is not defined - no volume and no volume_name exist
                # make sure the combination of volume_name and volume_id is unique on the storage
                # next command will fail if multiple found
                testUnique = self.volume_name_to_volume_id()
                return False
            else:
                # volume exists
                if self.params['volume_name'] == '':
                    # no name was given so the current one on the storage is the right one
                    return True
                else:
                    # check given name and current name are same
                    if self.params['volume_name'] == result['result'][str(self.params['volume_id'])]['LDEV_NAMING']:
                        # the are same
                        # make sure the combination of volume_name and volume_id is unique on the storage
                        # next command will fail if multiple found
                        testUnique = self.volume_name_to_volume_id()
                        return True
                    else:
                        # the are NOT same but must be
                        self.module.fail_json(
                            msg='volume_name and volume_id error - volume_id was given and the volume was found on the storage but the given volume_name does not match the current defined. Renaming was deemed a too dangerous operation. Please check and correct the inconsistency manually.')

    def volume_get_size(self):  # (in blocks)
        if self.params['volume_id'] == '':
            self.params['volume_id'] = self.volume_name_to_volume_id()
            if self.params['volume_id'] == '':
                return 0
        result = {}
        result['result'] = self.mystorage.getldev(
            ldev_id=self.params['volume_id']).view
        # return volume_getsize
        return result['result'][str(self.params['volume_id'])]['VOL_Capacity(BLK)']

    def volume_expand(self):
        if self.params['volume_id'] == '':
            self.params['volume_id'] = self.volume_name_to_volume_id()
            if self.params['volume_id'] == '':
                # volume with this name not found, create it and return result
                return self.volume_create(self)
                # self.module.fail_json(msg='volume_name and volume_id error - volume_name is NOT found on storage')
        # volume_id is no set, expand
        expand = self.mystorage.extendldev(
            ldev_id=self.params['volume_id'], capacity=self.params['volume_size'])
        return vars(expand)

    def volume_create(self):
        if self.params['volume_id'] == '':
            # use the next free ldev_id
            # old: self.params['volume_id'] = self.mystorage.getnextfreeldev()['ldev']
            # this needs review as the static ranges do not match all Hitachi storage models
            createTemp = self.mystorage.addldevauto(
                ldev_id=self.params['volume_id'], poolid=self.params['pool_id'], capacityblk=self.params['volume_size'], resource_id=0, start=0, end=5000)
            # self.module.fail_json(msg=' %s' % json.dumps(create))
            self.params['volume_id'] = createTemp["ID"]
            create = self.mystorage.getldev(
                ldev_id=self.params['volume_id']).view
            # self.module.fail_json(msg=' %s' % json.dumps(create))
        else:
            create = vars(self.mystorage.addldev(
                ldev_id=self.params['volume_id'], poolid=self.params['pool_id'], capacity=self.params['volume_size']))
        if not self.params['volume_name'] == "":
            modify_ldevname = self.mystorage.modifyldevname(
                ldev_id=self.params['volume_id'], ldev_name=self.params['volume_name'])
        # return vars(create)
        return create

    def volume_set_name(self):
        modify_ldevname = self.mystorage.modifyldevname(
            ldev_id=self.params['volume_id'], ldev_name=self.params['volume_name'])
        return vars(modify_ldevname)

    def volume_delete(self):
        if self.params['volume_id'] == '':
            self.params['volume_id'] = self.volume_name_to_volume_id()
            if self.params['volume_id'] == '':
                # volume with volume_name was not found, hence it was already deleted
                return {}
                # self.module.fail_json(msg='volume_name and volume_id error - volume_name is NOT found on storage')
        delete = self.mystorage.deleteldev(ldev_id=self.params['volume_id'])
        return vars(delete)

    # #####
    # # hostgroup management
    # #####

    def host_grp_get_facts(self):
        result = {}
        cmdreturn = self.mystorage.gethostgrp_key_detail(port=self.params['port'],datafilter={'GROUP_NAME':self.params['host_grp_name']})
        result['facts'] = cmdreturn.data
        result['changed'] = False
        return result

    # #####
    # # HUR management
    # #####

    def hur_status(self):
        pairdisplay = self.mystorage.cci.pairdisplayx(
            inst=self.horcm_inst, group=self.params['copy_group'],opts=self.params['options'])
        #return pairdisplay['pairdisplaydata']['pairs'][self.params['copy_group']]
        return pairdisplay
        # self.module.fail_json(msg=(pairdisplay['pairdisplaydata']['pairs'][self.params['copy_group']]))

    def hur_create(self):
        paircreate = self.mystorage.cci.paircreate(
            inst=self.horcm_inst, group=self.params['copy_group'], mode='H', jp=self.params['journal_primary'], js=self.params['journal_secondary'], fence='async 10')
        return paircreate

    def hur_delete(self):
        pairdelete = self.mystorage.cci.pairsplit(
            inst=self.horcm_inst, group=self.params['copy_group'], opts='-S')
        return pairdelete

    def hur_split(self):
        pairsplit = self.mystorage.cci.pairsplit(
            inst=self.horcm_inst, group=self.params['copy_group'], opts=self.params['options'])
        return pairsplit

    def hur_resync(self):
        pairresync = self.mystorage.cci.pairresync(
            inst=self.horcm_inst, group=self.params['copy_group'], mode='H')
        return pairresync

    def hur_takeover(self):
        pairtakeover = self.mystorage.cci.pairtakeover(
            inst=self.horcm_inst, group=self.params['copy_group'], mode='H', timeout=self.params['timeout'])
        return pairtakeover
    
    def hur_chkdsp(self):
        raidvchkdsp = self.mystorage.cci.raidvchkdsp(
            inst=self.horcm_inst, group=self.params['copy_group'], mode='H')
        return raidvchkdsp
