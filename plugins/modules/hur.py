#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2023 Hitachi Vantara, Inc. All rights reserved.
# Author: Giacomo Chiapparini <@gchiapparini-hv>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)


from __future__ import absolute_import, division, print_function
__metaclass__ = type

ANSIBLE_METADATA = {'metadata_version': '0.0.2',
                    'status': ['development'],
                    'supported_by': 'community'}

DOCUMENTATION = r'''
---
module: hur
version_added: "0.0.1"
short_description: Manage Hitachi VSP Storage asynchronous Hitachi Universal Replication (hur)
description:
- Use this module to manage Hitachi VSP storage hur groups as defined in a horcm file. This module allows
  you to pair, split, or horctakover them.
author:
- Giacomo Chiapparini (@gchiapparini-hv) raidcomansible@hitachivantara.com
options:
  horcm_inst:
    description:
    - ID for the HORCM instance.
    - HORCM inst can be created manually or by horcm-start.py.
    type: int
    required: true
  storage_serial:
    description:
    - storage serial ID. (e.g 495101).
    type: int
    required: false
  state:
    description:
    - Either create/expand(present) or delete(absent) or query a volume.
    type: str
    required: true
    choices: [ absent, present, query ]
  copy_group:
    description:
    - The specific copy_group name as defined in the horcm file
    type: str
    required: true
  
requirements:
- CCI/raidcom CLI software from support.hitachivantara.com (customer login required)
- horcm.conf file, horcmstart and login done (work is in progress to automate this)
notes:
- Supports C(check_mode).
- Supports D(diff_mode).
'''

EXAMPLES = r'''
  - name: get copy_group pairstatus (pairdisplay)
    hur:
      #connectivity
      horcm_inst: "1"
      storage_serial: "495101"
      #properties
      state: query
      copy_group: "hur"

'''

RETURN = r'''
changed:
    description: wheter or not the resouruce was changed
    returned: always
    type: bool
diff:
    description: status "before" and "after"
    returned: when -D is used
    type: dict
facts:
    description: response as return number, stderr and stdout
    returned: when a call is needed
    type: dict
invocation.module_args:
    description: all properties sent
    returned: always
    type: dict
item:
    description: copy_group
    returned: always
    type: str
message:
    description: status and activity
    returned: always
    type: str
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.hitachi.raidcom.plugins.module_utils.hitachi_raidcom import hitachi_raidcom, hitachi_raidcom_argument_spec


def run_module():

    # # define available arguments/parameters a user can pass to the module
    # # add here the module specific values provided by the playbook
    argument_spec = {
        "state": {"required": True, "type": "str", "choices": ["absent", "present", "resynced", "splitted", "takeover", "display", "query", "chkdsp"]},
        "copy_group": {"required": True, "type": "str"},
        "timeout": {"required": False, "type": "int", "default": 60},
        "journal_primary": {"required": False, "type": "int"},
        "journal_secondary": {"required": False, "type": "int"},
        "options": {"required": False, "type": "str", "choices": ["-RB", "-rw", "-r", "-S","-l"]},
        # only used in split 
        # -RB (SSWS to SSUS(PSUE)), -rw (ReadWrite), -r (ReadOnly), -S (Simplex=Delete Replication)
    }

    argument_spec.update(hitachi_raidcom_argument_spec)
    # seed the result dict in the object
    # we primarily care about changed and state
    # change is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = dict(
        changed=False,
        original_message='',
        message='',
        facts={}  # facts=dict() pylint complains
    )

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    raidcom = hitachi_raidcom(module)

    # if the user is working with this module in only check mode we do not
    # make any changes to the environment
    # for now just acknowledge we run in check mode and are aware of
    result['facts'] = {}  # result['facts'] = dict() pylint complains
    # Check mode should not print anything. A warning would help me to understand better if checkmode was active.
    # if module.check_mode:
    #    module.warn('*** Check Mode Active *** No changes will be executed !')

    # query/display: get current hur pair status information
    if (module.params["state"] == "query") or (module.params["state"] == "display"):
        result['facts'] = raidcom.hur_status()
        result['changed'] = False

    # present: pair create
    if module.params["state"] == "present":
        result['facts'] = raidcom.hur_create()
        result['changed'] = True

    # absent: pair delete (simplex)
    if module.params["state"] == "absent":
        result['facts'] = raidcom.hur_delete()
        result['changed'] = True

    # absent: pair splitted (psus/ssus)
    if module.params["state"] == "splitted":
        result['facts'] = raidcom.hur_split()
        result['changed'] = True

    # absent: pair resync
    if module.params["state"] == "resynced":
        result['facts'] = raidcom.hur_resync()
        result['changed'] = True

    # absent: pair horctakeover
    if module.params["state"] == "takeover":
        result['facts'] = raidcom.hur_takeover()
        result['changed'] = True
        
    # absent: pair raidvchkdsp
    if module.params["state"] == "chkdsp":
        result['facts'] = raidcom.hur_chkdsp()
        result['changed'] = False

    # query/display: get current hur pair status information
    #if module.params["state"] == "splitted":
    #    result['facts'] = raidcom.hur_split()
    #    #result['changed'] = False

    module.exit_json(**result)

# Main
def main():
    run_module()


if __name__ == '__main__':
    main()
