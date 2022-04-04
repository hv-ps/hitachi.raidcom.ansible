#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2021 Hitachi Vantara, Inc. All rights reserved.
# Author: Giacomo Chiapparini <@gchiapparini-hv>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)


from __future__ import absolute_import, division, print_function
__metaclass__ = type

ANSIBLE_METADATA = {'metadata_version': '0.5.0',
                    'status': ['preview'],
                    'supported_by': 'community'}

DOCUMENTATION = r'''
---
module: volume
version_added: "0.5.0"
short_description: Manage Hitachi VSP Storage volumes
description:
- Use this module to manage Hitachi VSP storage volumes. This module allows
  you to create volumes, update, or delete them.
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
  volume_name:
    description:
    - The specific volume_name.
    - When unset, this parameter defaults to empty string.
    - NOTE currently volume_name can not be used to select a volume for midification, use I(volume_id).
    type: str
    default: ""
    required: false
  volume_id:
    description:
    - The specific ID in decimal that should be modified/queried.
    - This parameter is always required.
    - NOTE currently only decimal format (e.g 100) is accepted not hexadecimal (e.g 00:00:64).
    type: str
    required: true
  pool_id:
    description:
    - The specific ID in decimal that selects the pool where the volume is in.
    - Required if I(state=present).
    type: str
    default: "0"
    required: false
  volume_size:
    description:
    - The specific volume size.
    - Required if I(state=present).
    - Capacity can be set in blocks (blank number) or as KB,K,MB,M,TB,T,PB,P (e.g 100GB).
    - NOTE currently KB or Kb or K is always KB = 1024.
    type: str
    required: false
  data_saving_type:
    description:
    - Wheter capacity saving should be disabled or enabled.
    - When unset, this parameter defaults to disabled (Former storage systems do not support this feature.).
    - NOTE this feature is not yet implemented.
    type: str
    choices: [ '', disabled, compression, deduplication_and_compression ]
    default: "disabled"
    required: false
  alua:
    description:
    - Wheter ALUA multipathing feature should be enabled or disable for this volume on this storage.
    - When unset, this parameter defaults to disabled.
    - NOTE this feature is not yet implemented, alua is always disabled.
    type: str
    default: "disabled"
    choices: [ "disabled", "enabled" ]
    required: false
  volume_type:
    description:
    - Wheter this is a thin allocated volume or not.
    - When unset, this parameter defaults to thin.
    - NOTE this feature is not yet implemented, all volumes are thin.
    type: str
    default: "thin"
    choices: [ "thin" ]
    required: false
  tiering_policy_id:
    description:
    - The specific tiering policiy id this volume should be assigned. Takes only effect if POOL is a Hitachi Dynamic Tiering (HDT) pool.
    - When unset, this parameter defaults to 0.
    type: str
    choices: ["0","1","2","3","4","5","6","7","8","9"]
    required: false
requirements:
- CCI/raidcom CLI software from support.hitachivantara.com (customer login required)
- horcm.conf file, horcmstart and login done (work is in progress to automate this)
notes:
- if both volume name and volume id are given - volume id is used to select
- Supports C(check_mode).
- Supports D(diff_mode).
'''

EXAMPLES = r'''
  - name: get volume information
    volume:
      #connectivity
      horcm_inst: "1"
      storage_serial: "495101"
      #properties
      state: query
      volume_id: "100"

  - name: create or expand volume
    volume:
      #connectivity
      horcm_inst: "1"
      storage_serial: "495101"
      #properties
      state: present
      volume_id: "100"
      volume_size: 200 GB

  - name: delete volume
    volume:
      #connectivity
      horcm_inst: "1"
      storage_serial: "495101"
      #properties
      state: absent
      volume_id: "100"
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
    description: volume id
    returned: always
    type: int
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
        "state": {"required": True, "type": "str", "choices": ["absent", "present", "query"]},
        "volume_name": {"required": False, "type": "str", "default": ""},
        "volume_id": {"required": True, "type": "str"},
        "pool_id": {"required": False, "type": "str", "default": "0"},
        "volume_size": {"required": False, "type": "str"},
        "data_saving_type": {"required": False, "type": "str", "default": "disabled",
                             "choices": ["", "disabled", "compression", "deduplication_and_compression"]},
        "alua": {"required": False, "type": "str", "default": "disabled", "choices": ["disabled", "enabled"]},
        "volume_type": {"required": False, "type": "str", "default": "thin", "choices": ['thin']},
        "tiering_policy_id": {"required": False, "type": "str", "choices": ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]},
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
        required_if=[
            ['state', 'absent', ['volume_id']],
            ['state', 'present', ['volume_id', 'volume_size']],
            ['state', 'query', ['volume_id']]
        ],
    )

    raidcom = hitachi_raidcom(module)
    currentVolumeSizeBlocks = 0
    targetVolumeSizeBlocks = 0

    # if the user is working with this module in only check mode we do not
    # make any changes to the environment
    # for now just acknowledge we run in check mode and are aware of
    result['facts'] = {}  # result['facts'] = dict() pylint complains
    # Check mode should not print anything. A warning would help me to understand better if checkmode was active.
    # if module.check_mode:
    #    module.warn('*** Check Mode Active *** No changes will be executed !')

    # query: get information
    if module.params["state"] == "query":
        result['facts'] = raidcom.volume_get_properties()
        result['changed'] = False

    # present: create or modify a volume
    if module.params["state"] == "present":

        # convert targetSize to Blocks
        targetVolumeSizeBlocks = raidcom.convertSizeToBlocks(module.params['volume_size'])

        # find out if the volume already exists
        if (raidcom.volume_exists()):
            # yes exists
            # check if volume size is same or needs to be expanded
            currentVolumeSizeBlocks = int(raidcom.volume_get_size())
            differenceVolumeSizeBlocks = targetVolumeSizeBlocks - currentVolumeSizeBlocks
            # DEBUG
            # raise Exception(raidcom.volume_get_size())
            # raise Exception(module.params['volumeSize'])
            # module.warn('volumeSize: %s' % module.params['volumeSize'])
            # module.warn('getSize: %s' % raidcom.volume_get_size())
            # module.warn('difference: %s' % differenceVolumeSizeBlocks)

            if targetVolumeSizeBlocks <= currentVolumeSizeBlocks:
                # volume already exists, size is same (or smaller, but shrinking is not possible)
                if targetVolumeSizeBlocks < currentVolumeSizeBlocks:
                    # volume size smaller, but shrinking is not possible, fail
                    result['facts'] = raidcom.volume_get_properties()
                    result['message'] = 'volume already exists and size is smaller, shrinking not possible, fail. Current size: ' + \
                                        str(raidcom.blkstomb(currentVolumeSizeBlocks)) + ' Requested size: ' + str(raidcom.blkstomb(targetVolumeSizeBlocks))
                    result['msg'] = 'volume already exists and size is smaller, shrinking not possible, fail. Current size: ' + \
                                    str(raidcom.blkstomb(currentVolumeSizeBlocks)) + ' Requested size: ' + str(raidcom.blkstomb(targetVolumeSizeBlocks))
                    # Difference - but we need to fail as we can not reach target -> stop with error
                    # result['diff'] =  {'after': 'volume_id ' + str(module.params['volume_id']) +
                    #  ' exists, same size ' + str(raidcom.blkstomb(currentVolumeSizeBlocks)) + '. Can not shrinnk!' + '\n',
                    #  'before': 'volume_id ' + str(module.params['volume_id']) + ' exists, size ' + str(raidcom.blkstomb(currentVolumeSizeBlocks)) + '\n'}
                    result['changed'] = False
                    module.fail_json(**result)
                else:
                    result['facts'] = raidcom.volume_get_properties()
                    result['message'] = 'volume already exists, same size, nothing to do'
                    # No difference - print nothing
                    # result['diff'] =  {'after': 'volume_id ' + str(module.params['volume_id']) +
                    #  ' exists, same size ' + str(raidcom.blkstomb(targetVolumeSizeBlocks)) + '\n',
                    #  'before': 'volume_id ' + str(module.params['volume_id']) + ' exists, same size ' + str(raidcom.blkstomb(targetVolumeSizeBlocks)) + '\n'}
                    result['changed'] = False

            else:
                # expand the volume
                # raidcom expand needs the size difference, ansible user provides final size
                module.params['volume_size'] = differenceVolumeSizeBlocks
                if not module.check_mode:
                    result['facts'] = raidcom.volume_expand()
                result['message'] = 'volume already exists, size was expanded'
                result['diff'] = {'after': 'volume_id ' + str(module.params['volume_id']) +
                                  ' expanded to ' + str(raidcom.blkstomb(targetVolumeSizeBlocks)) + '\n',
                                  'before': 'volume_id ' + str(module.params['volume_id']) + ' exists ' + str(raidcom.blkstomb(currentVolumeSizeBlocks)) + '\n'}
                result['changed'] = True
        else:
            # volume does not exist, create it
            module.params['volume_size'] = targetVolumeSizeBlocks
            if not module.check_mode:
                result['facts'] = raidcom.volume_create()
            result['message'] = 'volume does not exists, create it'
            result['diff'] = {'after': 'volume_id ' + str(module.params['volume_id']) + ' created ' + str(raidcom.blkstomb(targetVolumeSizeBlocks)) +
                              '\n', 'before': 'volume_id ' + str(module.params['volume_id']) + ' does not exist' + '\n'}
            result['changed'] = True

    # absent = delete a volume
    if module.params["state"] == "absent":
        # find out if the volume already exists
        if (raidcom.volume_exists()):
            # does exist, delete it
            currentVolumeSizeBlocks = int(raidcom.volume_get_size())
            if not module.check_mode:
                result['facts'] = raidcom.volume_delete()
            result['message'] = 'volume_id ' + str(module.params['volume_id']) + ' exists, delete it'
            result['diff'] = {'after': 'volume_id ' + str(module.params['volume_id']) + ' deleted' + '\n',
                              'before': 'volume_id ' + str(module.params['volume_id']) + ' exists ' + str(raidcom.blkstomb(currentVolumeSizeBlocks)) + '\n'}
            result['changed'] = True
        else:
            # it does not exist
            # nothing to do
            result['facts'] = {}  # result['facts'] = dict() pylint complains
            result['message'] = 'volume does not exist, nothing to do'
            # No difference - print nothing
            # result['diff'] = {'after': 'volume_id ' + str(module.params['volume_id']) + ' still does not exist' + '\n',
            #          'before': 'volume_id ' + str(module.params['volume_id']) + ' does not exist ' + '\n'}
            result['changed'] = False

    # during the execution of the module, if there is an exception or a
    # conditional state that effectively causes a failure, run
    # AnsibleModule.fail_json() to pass in the message and the result
    # if module.params['name'] == 'fail me':
    #    module.fail_json(msg='You requested this to fail', **result)

    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    # module.exit_json(changed=False)
    # module.exit_json(changed=result['changed'], ansible_facts=result['facts'])
    # module.fail_json(msg='You requested this to fail')
    module.exit_json(**result)


# Main
def main():
    run_module()


if __name__ == '__main__':
    main()
