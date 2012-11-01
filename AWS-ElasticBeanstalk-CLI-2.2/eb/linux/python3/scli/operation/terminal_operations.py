#!/usr/bin/env python
#==============================================================================
# Copyright 2012 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Amazon Software License (the "License"). You may not use
# this file except in compliance with the License. A copy of the License is
# located at
#
#       http://aws.amazon.com/asl/
#
# or in the "license" file accompanying this file. This file is distributed on
# an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, express or
# implied. See the License for the specific language governing permissions
# and limitations under the License.
#==============================================================================
import logging as _logging

from lib.rds import rds_utils
from scli.constants import ServiceEndpoint
from scli.constants import ParameterName
from scli.constants import ParameterSource
from scli.parameter import Parameter
from scli.operation.base import OperationBase
from scli.operation.base import OperationResult
from scli.terminal.terminal import Terminal

log = _logging.getLogger('cli.op')

class AskForMissiongParameterOperation(OperationBase):
    ''' Fill missing parameters using interactive interface '''
        
    _input_parameters = set()
    
    _output_parameters = set()
    
    def execute(self, parameter_pool):
        self._generate_service_endpoint(parameter_pool)
        self._check_rds_parametr(parameter_pool)
        
        required_params = self._operation_queue.required_parameters
        missing_params = required_params - parameter_pool.parameter_names
        if len(missing_params) > 0:
            terminal = Terminal()
            terminal.ask_parameters(parameter_pool, missing_params, True)

        ret_result = OperationResult(self, None, None, None)
        return ret_result

    def _generate_service_endpoint(self, pool):
        ''' 
        Generate EB service endpoint from region if not presents, or overwrite
        if specified region has higher priority.
        '''
        if pool.has(ParameterName.Region) and \
            (not pool.has(ParameterName.ServiceEndpoint) or \
             ParameterSource.is_ahead(pool.get_source(ParameterName.Region), 
                                     pool.get_source(ParameterName.ServiceEndpoint))):
            region = pool.get(ParameterName.Region)
            log.info('Generate service endpoint from region "{0}".'.format(region.value))
            pool.put(Parameter(ParameterName.ServiceEndpoint, 
                                ServiceEndpoint[region.value], 
                                region.source))        

    def _check_rds_parametr(self, pool):
        stack_name = pool.get_value(ParameterName.SolutionStack)\
            if pool.has(ParameterName.EnvironmentName) else None
        rds_enable = pool.get_value(ParameterName.RdsEnabled) \
            if pool.has(ParameterName.RdsEnabled) else None
            
        if rds_enable and rds_utils.is_require_rds_parameters(pool)\
            and rds_utils.is_rds_snippet_compatible(pool, stack_name):
            self._input_parameters.add(ParameterName.RdsSourceSnapshotName)
            self._input_parameters.add(ParameterName.RdsMasterPassword)
            self._input_parameters.add(ParameterName.RdsDeletionPolicy)
            
    
class AskForConfigFileParameterOperation(OperationBase):
    ''' Ask all parameters using interactive interface '''
        
    _input_parameters = set()
    
    _output_parameters = set()
    
    def execute(self, parameter_pool):
        
        parameters = {ParameterName.AwsAccessKeyId,
                      ParameterName.AwsSecretAccessKey,
                      ParameterName.Region,
                      ParameterName.SolutionStack,
                      ParameterName.ApplicationName,
                      ParameterName.EnvironmentName,
                      ParameterName.RdsEnabled,
                      }
        
        terminal = Terminal()
        terminal.ask_parameters(parameter_pool, parameters, False)

        ret_result = OperationResult(self, None, None, None)
        return ret_result    
    
    