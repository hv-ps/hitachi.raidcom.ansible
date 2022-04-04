#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2021 Hitachi Vantara, Inc. All rights reserved.
# Author: Darren Chambers <@Darren-Chambers>
# Author: Giacomo Chiapparini <@gchiapparini-hv>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)


from __future__ import absolute_import, division, print_function
__metaclass__ = type

import subprocess
import time
from ansible_collections.hitachi.raidcom.plugins.module_utils.hitachi_raidcom_utility_parser import raidcom_parser
import inspect
import os
import json
import re


class raidcom:
    def __init__(self, serial, instance, path="/usr/bin/", cciextension='.sh'):
        self.serial = serial
        self.instance = instance
        self.path = path
        self.parser = raidcom_parser(self, serial)
        self.successfulcmds = []
        self.cciextension = cciextension
        self.cmdoutput = False

    def execute(self, cmd, undocmds=[], expectedreturn=0):
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, shell=True)
        stdout, stderr = proc.communicate()
        if proc.returncode and proc.returncode != expectedreturn:
            message = {'return': proc.returncode, 'stdout': stdout, 'stderr': stderr}
            raise Exception('Unable to execute Command "{}". Command dump > {}'.format(cmd, message))
        return {'return': proc.returncode, 'stdout': stdout, 'stderr': stderr}

    def getcommandstatus(self, *args, **kwargs):
        request_id = str(kwargs.get('request_id', ''))
        requestid_cmd = kwargs.get('requestid_cmd', '')
        if request_id:
            requestid_cmd = '-request_id {}'.format(request_id)
        cmd = '{}raidcom get command_status {} -I{} -s {}'.format(self.path, requestid_cmd, self.instance, self.serial)
        cmdreturn = self.execute(cmd)
        return cmdreturn

    def resetcommandstatus(self, *args, **kwargs):
        request_id = str(kwargs.get('request_id', ''))
        requestid_cmd = kwargs.get('requestid_cmd', '')
        if request_id:
            requestid_cmd = '-request_id {}'.format(request_id)
        cmd = '{}raidcom reset command_status {} -I{} -s {}'.format(self.path, requestid_cmd, self.instance, self.serial)
        cmdreturn = self.execute(cmd)
        return cmdreturn

    def getldev(self, *args, **kwargs):
        ldevid = kwargs.get('ldevid')
        cmd = '{}raidcom get ldev -ldev_id {} -I{} -s {}'.format(self.path, ldevid, self.instance, self.serial)
        cmdreturn = self.execute(cmd)
        cmdreturn['stdout'] = self.parser.getldev(cmdreturn['stdout'])
        return cmdreturn

    def getldevlist(self, *args, **kwargs):
        # {dp_volume | external_volume | journal | pool | parity_grp | mp_blade | defined | undefined | mapped | mapped_nvme | unmapped}
        ldevtype = kwargs.get('ldevtype')
        cmd = '{}raidcom get ldev -ldev_list {} -I{} -s {}'.format(self.path, ldevtype, self.instance, self.serial)
        cmdreturn = self.execute(cmd)
        cmdreturn['stdout'] = self.parser.getldevlist(cmdreturn['stdout'])
        return cmdreturn

    def getnextfreeldev(self, *args, **kwargs):
        cmd = '{}raidcom get ldev -ldev_list {} -I{} -s {}'.format(self.path, 'undefined', self.instance, self.serial)
        cmdreturn = self.execute(cmd)
        cmdreturn['stdout'] = self.parser.getldevlist(cmdreturn['stdout'])[0]
        return cmdreturn

    def extendvolume(self, *args, **kwargs):
        ldevid = str(kwargs.get('ldevid'))
        capacityblk = int(kwargs.get('capacityblk'))
        self.resetcommandstatus()
        cmd = '{}raidcom extend ldev -ldev_id {} -capacity {} -I{} -s {}'.format(self.path, ldevid, capacityblk, self.instance, self.serial)
        cmdreturn = self.execute(cmd)
        self.getcommandstatus()
        return cmdreturn

    def deletevolume(self, *args, **kwargs):
        ldevid = str(kwargs.get('ldevid'))
        self.resetcommandstatus()
        cmd = '{}raidcom delete ldev -ldev_id {} -I{} -s {}'.format(self.path, ldevid, self.instance, self.serial)
        cmdreturn = self.execute(cmd)
        self.getcommandstatus()
        return cmdreturn

    def modifyldevname(self, *args, **kwargs):
        ldevid = str(kwargs.get('ldevid'))
        ldev_name = str(kwargs.get('ldev_name'))
        cmd = '{}raidcom modify ldev -ldev_id {} -ldev_name {} -I{} -s {}'.format(self.path, ldevid, ldev_name, self.instance, self.serial)
        cmdreturn = self.execute(cmd)
        return cmdreturn

    def addldev(self, *args, **kwargs):
        ldevid = str(kwargs.get('ldevid'))
        poolid = int(kwargs.get('poolid'))
        capacityblk = int(kwargs.get('capacityblk'))
        self.resetcommandstatus()
        cmd = '{}raidcom add ldev -ldev_id {} -pool {} -capacity {} -I{} -s {}'.format(self.path, ldevid, poolid, capacityblk, self.instance, self.serial)
        cmdreturn = self.execute(cmd)
        self.getcommandstatus()
        return cmdreturn
