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

import time

from cortx.utils.log import Log
from cortx.utils.ha.dm.decision_monitor import DecisionMonitor
from cortx.utils.conf_store.conf_store import Conf

from ha.core.error import HAUnimplemented
from ha.core.node.replacement.refresh_context import PcsRefreshContex
from ha.execute import SimpleCommand
from ha.core.support_bundle.ha_bundle import HABundle, CortxHABundle
from ha import const
from ha.core.config.config_manager import ConfigManager

class ClusterManager:
    def __init__(self):
        """
        Manage cluster operation
        """
        pass

    def process_request(self, action, args):
        raise HAUnimplemented()

    def node_status(self, node):
        # TODO move node logic to node manager class
        raise HAUnimplemented()

    def remove_node(self, node):
        raise HAUnimplemented()

    def add_node(self, node):
        raise HAUnimplemented()

    def start(self):
        raise HAUnimplemented()

    def stop(self):
        raise HAUnimplemented()

    def status(self):
        raise HAUnimplemented()

    def shutdown(self):
        raise HAUnimplemented()

class PcsClusterManager(ClusterManager):
    def __init__(self):
        """
        PcsCluster manage pacemaker/corosync cluster
        """
        super(PcsClusterManager, self).__init__()
        self._execute = SimpleCommand()

        # get version from ha.conf
        version = ConfigManager.get_major_version()
        major_version = version.split('.')
        self._version = major_version[0]

        if self._version == const.CORTX_VERSION_1:
            self._decision_monitor = DecisionMonitor()
            # TODO: add node_manager class to handle query
            self._refresh_contex = PcsRefreshContex(self._decision_monitor)
            # TODO move node logic to node manager class
            self._node_status = [ 'Online', 'Standby', 'Maintenance', 'Offline', 'Disconnected']

    def process_request(self, action, args, output):
        """
        Generic method to handle process request

        Args:
            action ([string]): Take cluster action for each request.
            args ([dict]): Parameter pass to request to process.
        """
        self._output = output
        # TODO Add validater
        if action == const.CLUSTER_COMMAND:
            if args.cluster_action in ["add_node", "remove_node"]:
                getattr(self, args.cluster_action)(args.node)
            else:
                getattr(self, args.cluster_action)()
        elif action == const.NODE_COMMAND and self._version == const.CORTX_VERSION_1:
            self._refresh_contex.process_request(action, args)
        elif action == const.BUNDLE_COMMAND:
            HABundle().process_request(action, args, output)
        else:
            raise HAUnimplemented("This feature is not supported...")

    def node_status(self, node):
        """
        Check node status
        If node not detected return rc as 1 else 0
        Node status:
         Online:
         Standby:
         Maintenance:
         Offline:
        """
        Log.debug(f"Check {node} node status")
        # TODO: check is node is valid
        # TODO move node logic to node manager class
        _output, _err, _rc = self._execute.run_cmd("pcs status nodes")
        for status in _output.split("\n"):
            if node in status.split():
                node_rc = 0
                node_status = (status.split()[0])[:-1]
                Log.debug(f"For {node} node rc: {node_rc}, status: {node_status}")
                return node_rc, node_status
        Log.debug(f"{node} is not detected in cluster, treating as disconnected node")
        return 1, const.NODE_DISCONNECTED

    def remove_node(self, node):
        """
        Remove node from pcs cluster
        """
        # TODO: Limitation for node remove (in cluster node cannot remove it self)
        # Check if node already removed
        _output, _err, _rc = self._execute.run_cmd(const.PCS_STATUS)
        Log.info(f"Cluster status output before remove node: {_output}, {_err}, {_rc}")
        _rc, status = self.node_status(node)
        if _rc != 1:
            self._execute.run_cmd(f"pcs cluster node remove {node} --force")
            _rc, status = self.node_status(node)
            Log.debug(f"For node {node} status: {status}, rc: {_rc}")
            if _rc != 1:
                Log.error(f"Failed to remove {node}")
                raise Exception(f"Failed to remove {node}")
            else:
                Log.info(f"Node {node} removed from cluster")
        else:
            Log.info(f"Node {node} already removed from cluster")
        _output, _err, _rc = self._execute.run_cmd(const.PCS_STATUS)
        Log.info(f"Cluster status output after remove node: {_output}, {_err}, {_rc}")

    def add_node(self, node):
        """
        Add new node to pcs cluster
        """
        _output, _err, _rc = self._execute.run_cmd(const.PCS_STATUS)
        Log.info(f"Cluster status output before add node: {_output}, {_err}, {_rc}")
        # TODO: Limitation for node add (in cluster node cannot add it self)
        commands = [f"pcs cluster node add {node}",
                f"pcs cluster enable {node}",
                f"pcs cluster start {node}",
                "pcs resource cleanup --all"]
        _rc, status = self.node_status(node)
        if _rc != 0:
            for command in commands:
                _output, _err, _rc = self._execute.run_cmd(command)
                Log.info(f"{command} : {_output}, {_err}, {_rc}")
                time.sleep(5)
            retries = 0
            add_node_flag = -1
            while retries < 12:
                _rc, status = self.node_status(node)
                Log.info(f"{node} status rc: {_rc}, status: {status}")
                if status == const.NODE_ONLINE:
                    Log.info(f"Node {node} added to cluster")
                    add_node_flag = 0
                    break
                elif status != const.NODE_DISCONNECTED:
                    add_node_flag = 1
                    Log.info(f"Node {node} added to cluster but not Online check status again.")
                retries += 1
                time.sleep(10)
            if add_node_flag == 1:
                Log.info(f"Node {node} added to cluster but not in Online state.")
            elif add_node_flag == 0:
                Log.info(f"Node {node} Successfully added to cluster and in Online state")
            else:
                raise Exception(f"Failed to add {node} to cluster")
        else:
            Log.info(f"Node {node} already added to cluster")
        _output, _err, _rc = self._execute.run_cmd(const.PCS_STATUS)
        Log.info(f"Cluster status output after add node: {_output}, {_err}, {_rc}")

    def get_nodes_status(self):
        """
        Sample output of the const.PCS_STATUS_NODES command

        Pacemaker Nodes:
         Online: node1 node2
         Standby:
         Standby with resource(s) running:
         Maintenance:
         Offline:
        Pacemaker Remote Nodes:
         Online:
         Standby:
         Standby with resource(s) running:
         Maintenance:
         Offline:
        """
        _output, _err, _rc = self._execute.run_cmd(const.PCS_STATUS_NODES, check_error=False)

        self.active_nodes = self.standby_nodes = self.offline_nodes = "false"
        for status in _output.split("\n"):
            nodes = status.split()
            if len(nodes) > 0:
                if nodes[0] == "Online:" and len(nodes) > 1:
                    self.active_nodes = "true"

                if nodes[0] == "Standby" and nodes[1] == "with" and nodes[2] == "resource(s)" and nodes[3] == "running:" and len(nodes) > 4:
                    self.active_nodes = "true"

                if((nodes[0] == "Maintenance:") and (len(nodes) > 1)):
                    self.active_nodes = "true"

                if((nodes[0] == "Standby:") and (len(nodes) > 1)):
                    self.standby_nodes = "true"

                if((nodes[0] == "Offline:") and (len(nodes) > 1)):
                    self.offline_nodes = "true"


    def start(self):

        Log.debug("Executing cortxha cluster start")

        _output, _err, _rc = self._execute.run_cmd(const.PCS_CLUSTER_STATUS, check_error=False)
        if _rc != 0:
            if(_err.find("No such file or directory: 'pcs'") != -1):
                Log.error("Cluster failed to start; pcs not installed")
                self._output.output("Cluster failed to start; pcs not installed")
                self._output.rc(1)
                raise Exception("Cluster failed to start; pcs not installed")
            # if cluster is not running; start cluster
            elif(_err.find("cluster is not currently running on this node") != -1):
                self._execute.run_cmd(const.PCS_CLUSTER_START, check_error=False)
                Log.info("cluster started ; waiting for nodes to come online ")
                # It takes nodes 30 seconds to come to their original state after cluster is started
                # observation on a 2 node cluster
                # wait for upto 100 sec for nodes to come to active states (online / maintenance mode)
                time.sleep(10)
                self.get_nodes_status()
                retries = 18
                while  self.active_nodes == "false" and retries > 0:
                    time.sleep(5)
                    self.get_nodes_status()
                    retries -= 1

        else:
            #If cluster is running, but all nodes are  in Standby mode;
            #start the nodes
            self.get_nodes_status()
            if self.active_nodes == "false":
                if self.standby_nodes == "true":
                    # issue pcs cluster unstandby
                    _output, _err, _rc = self._execute.run_cmd(const.PCS_CLUSTER_UNSTANDBY, check_error=False)

        # check cluster and node status
        output, _err, _rc = self._execute.run_cmd(const.PCS_CLUSTER_STATUS, check_error=False)
        if _rc != 0:
            # cluster could not be started.
            Log.error("Cluster failed to start")
            self._output.output("Cluster failed to start")
            self._output.rc(1)
            raise Exception("Cluster failed to start")
        else:
            # confirm that at least one node is active
            self.get_nodes_status()
            if self.active_nodes == "false":
                # wait for 5 seconds and retry
                time.sleep(5)
                self.get_nodes_status()
                if self.active_nodes == "false":
                    self._output.output("Cluster started; nodes not online")
                    self._output.rc(1)
                    raise Exception("Cluster started; nodes not online")

        Log.info("Cluster started successfully")


    def stop(self):
        # TODO Add wrapper to hctl pcswrap
        raise HAUnimplemented("This feature is not supported...")

    def status(self):
        # TODO Add wrapper to hctl pcswrap
        raise HAUnimplemented("This feature is not supported...")

    def shutdown(self):
        raise HAUnimplemented("This feature is not supported...")

class CortxClusterManager:
    def __init__(self):
        """
        Manage cluster operation
        """
        self._execute = SimpleCommand()

    def process_request(self, action, args, output):
        """
        Process cluster request

        Args:
            action (string): action taken on cluster
            args (dictonery): parameteter
            output (object): Store output

        Raises:
            HAUnimplemented: [description]
        """
        # TODO: Provide service and node management
        self._output = output
        if action == const.CLUSTER_COMMAND:
            getattr(self, args.cluster_action)()
        elif action == const.BUNDLE_COMMAND:
            CortxHABundle().process_request(action, args, output)
        else:
            raise HAUnimplemented("This feature is not supported...")

    def remove_node(self):
        raise HAUnimplemented("Cluster remove node is not supported.")

    def add_node(self):
        raise HAUnimplemented("Cluster add node is not supported.")

    def start(self):
        Log.debug("Executing cluster start")
        _output, _err, _rc = self._execute.run_cmd(const.HCTL_START, check_error=False)
        Log.info(f"IO stack started. Output: {_output}, Err: {_err}, RC: {_rc}")
        self.status()
        if self._output.get_rc() == 0:
            Log.info("Cluster started successfully")
            self._output.output("Cluster started successfully")
            self._output.rc(0)
        else:
            Log.error("Cluster failed to start")
            self._output.output("Cluster failed to start")
            self._output.rc(1)

    def stop(self):
        Log.info("Executing cluster Stop")
        _output, _err, _rc = self._execute.run_cmd(const.HCTL_STOP, check_error=False)
        Log.info(f"Io stack stopped successfully. Output: {_output}, Err: {_err}, RC: {_rc}")
        self.status()
        if self._output.get_rc() == 1:
            Log.info("Cluster stopped successfully")
            self._output.output("Cluster stopped successfully...")
            self._output.rc(0)
        else:
            Log.error("Cluster failed to stop")
            self._output.output("Cluster failed to stop")
            self._output.rc(1)

    def status(self):
        _output, _err, _rc = self._execute.run_cmd(const.HCTL_STATUS, check_error=False)
        self._output.rc(_rc)
        status = const.HCTL_STARTED_STATUS if _rc == 0 else const.HCTL_STOPPED_STATUS
        self._output.output(status)

    def shutdown(self):
        raise HAUnimplemented("Cluster shutdown is not supported.")
