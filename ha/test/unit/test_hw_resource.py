#!/usr/bin/env python3

# Copyright (c) 2020 Seagate Technology LLC and/or its Affiliates
#
# This program is free software: you can redistribute it and/or modify it under the
# terms of the GNU Affero General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License along
# with this program. If not, see <https://www.gnu.org/licenses/>. For any questions
# about this software or licensing, please email opensource@seagate.com or
# cortx-questions@seagate.com.


"""
 ****************************************************************************
 Description:       resource_agent resource agent
 ****************************************************************************
"""

import os
import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

from cortx.utils.log import Log
from cortx.utils.ha.dm.actions import Action
from ha.resource.alert_monitor_resource_agent import HardwareResourceAgent
from ha import const

class TestHardwareResourceAgent(unittest.TestCase):
    """
    Unit test for hardware resource agent
    """

    def setUp(self):
        Log.init(service_name='resource_agent', log_path=const.RA_LOG_DIR, level="DEBUG")
        self.decision_monitor = MagicMock()
        self.filename = 'io_path_health_c1'
        self.path = 'io'
        self.decision_monitor.get_resource_group_status.side_effect = self._side_effect_group_status
        self.schema = {
            "nodes": {
                "27534128-7ecd-4606-bf42-ebc9765095ba": "cortxnode1.example.com",
                "f3c7d479-2249-40f4-9276-91ba59f50034": "cortxnode2.example.com",
                "local": "cortxnode1.example.com"
            }
        }
        self.status = None
        self.hw_agent = HardwareResourceAgent(self.decision_monitor, self.schema)

    def tearDown(self):
        if os.path.exists(const.HA_INIT_DIR + self.filename):
            os.remove(const.HA_INIT_DIR + self.filename)

    def _side_effect_group_status(self, key):
        if self.status is None:
            return Action.FAILED if key == self.path+'_'+self.schema['nodes']['local'] else Action.OK
        else:
            return self.status

    @patch('ha.resource.alert_monitor_resource_agent.HardwareResourceAgent.get_env')
    def test_start(self, patched_get_env):
        """
        Test start for hw resource agent

        Arguments:
            patched_get_env {[alert_monitor_resource_agent method]} -- Method for resource agent to get
                pacemaker env data.
        """
        patched_get_env.return_value = {
            'OCF_RESKEY_filename': self.filename,
            'OCF_RESKEY_path': self.path
        }
        self.status = Action.OK
        status = self.hw_agent.start()
        self.assertEqual(status, const.OCF_SUCCESS)
        self.status = None
        status = self.hw_agent.start()
        self.assertEqual(status, const.OCF_ERR_GENERIC)
        self.status = Action.RESOLVED
        status = self.hw_agent.start()
        self.assertEqual(status, const.OCF_SUCCESS)

    @patch('ha.resource.alert_monitor_resource_agent.HardwareResourceAgent.get_env')
    def test_stop(self, patched_get_env):
        """
        Test stop for hw resource agent

        Arguments:
            patched_get_env {[alert_monitor_resource_agent method]} -- Method for resource agent to get
                pacemaker env data.
        """
        patched_get_env.return_value = {
            'OCF_RESKEY_filename': self.filename,
            'OCF_RESKEY_path': 'io'
        }
        self.decision_monitor.get_resource_group_status.return_value = Action.FAILED
        status = self.hw_agent.stop()
        self.assertEqual(status, const.OCF_SUCCESS)
        status = self.hw_agent.stop()
        self.assertEqual(status, const.OCF_SUCCESS)

    @patch('ha.resource.alert_monitor_resource_agent.HardwareResourceAgent.get_env')
    def test_monitor(self, patched_get_env):
        """
        Test monitor for hw resource agent

        Arguments:
            patched_get_env {[alert_monitor_resource_agent method]} -- Method for resource agent to get
                pacemaker env data.
        """
        patched_get_env.return_value = {
            'OCF_RESKEY_filename': self.filename,
            'OCF_RESKEY_path': 'io'
        }
        os.makedirs(const.HA_INIT_DIR, exist_ok=True)
        if os.path.exists(const.HA_INIT_DIR + self.filename):
            os.remove(const.HA_INIT_DIR + self.filename)
        status = self.hw_agent.monitor()
        self.assertEqual(status, const.OCF_NOT_RUNNING)
        if not os.path.exists(const.HA_INIT_DIR + self.filename):
            with open(const.HA_INIT_DIR + self.filename, 'w'): pass
        self.status = Action.FAILED
        status = self.hw_agent.monitor()
        self.assertEqual(status, const.OCF_SUCCESS)
        self.status = None
        status = self.hw_agent.monitor()
        self.assertEqual(status, const.OCF_ERR_GENERIC)
        self.status = Action.OK
        status = self.hw_agent.monitor()
        self.assertEqual(status, const.OCF_SUCCESS)
        self.status = Action.RESOLVED
        status = self.hw_agent.monitor()
        self.assertEqual(status, const.OCF_SUCCESS)

if __name__ == "__main__":
    unittest.main()
