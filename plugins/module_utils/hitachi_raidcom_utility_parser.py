#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2021 Hitachi Vantara, Inc. All rights reserved.
# Author: Darren Chambers <@Darren-Chambers>
# Author: Giacomo Chiapparini <@gchiapparini-hv>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import re
import inspect
import sys


class raidcom_parser:
    def __init__(self, storage, serial):
        pass

    # Helper
    
    def convertstrtodict(self, stringtoconvert):
        return dict(map(str.strip, sub.split(':', 1)) for sub in stringtoconvert.split('\n') if ':' in sub)

    def convertstrofarrayofstrtodict(self, stringtoconvert):
        arraytoconvert = stringtoconvert.split('\n\n')
        result = []
        for item in arraytoconvert:
            result.insert(0,self.convertstrtodict(item))
        #some results contain a first empty entry {}, remove it
        if len(result[0]) == 0:
            result.pop(0)
        return result

    # Parser

    def getldev(self, stdout):
        ldevdict = self.convertstrtodict(stdout)
        return ldevdict

    def getldevlist(self, stdout):
        ldevlistdict = self.convertstrofarrayofstrtodict(stdout)
        return ldevlistdict



