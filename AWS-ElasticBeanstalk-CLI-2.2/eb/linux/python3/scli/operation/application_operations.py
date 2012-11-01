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

from scli import prompt  
from scli import config_file
from scli.constants import ParameterName
from scli.operation.base import OperationBase
from scli.operation.base import OperationResult
from scli.resources import CreateApplicationOpMessage
from scli.resources import DeleteApplicationOpMessage
from lib.elasticbeanstalk.servicecall import ElasticBeanstalkClient
from lib.elasticbeanstalk.exception import AlreadyExistException
from lib.elasticbeanstalk.exception import OperationInProgressException
from lib.rds import rds_utils

log = _logging.getLogger('cli.op')


class CreateApplicationOperation(OperationBase):

    _input_parameters = {
                         ParameterName.AwsAccessKeyId, 
                         ParameterName.AwsSecretAccessKey,
                         ParameterName.ServiceEndpoint, 
                         ParameterName.ApplicationName,
                        }
    
    _output_parameters = {
                          ParameterName.ApplicationName,
                         }

    
    def execute(self, parameter_pool):
        eb_client = ElasticBeanstalkClient(parameter_pool.get_value(ParameterName.AwsAccessKeyId), 
                                           parameter_pool.get_value(ParameterName.AwsSecretAccessKey),
                                           parameter_pool.get_value(ParameterName.ServiceEndpoint))

        app_name = parameter_pool.get_value(ParameterName.ApplicationName)

        try:
            response = eb_client.create_application(app_name)
            prompt.result(CreateApplicationOpMessage.Start.format(app_name))
        except AlreadyExistException:
            log.info('Application "{0}" already exists.'.format(app_name))
            prompt.result(CreateApplicationOpMessage.AlreadyExist.format(app_name))
   
            ret_result = OperationResult(self,
                                         None, 
                                         CreateApplicationOpMessage.AlreadyExist.format(app_name),
                                         None)
        else:
            log.info('Received response for CreateApplication call.')
            prompt.info(CreateApplicationOpMessage.Succeed.format(app_name))
            self._log_api_result(self.__class__.__name__, 'CreateApplication', response.result)            
    
            ret_result = OperationResult(self,
                                         response.request_id, 
                                         CreateApplicationOpMessage.Succeed.format(app_name),
                                         response.result)
            
        return ret_result
        


class DeleteApplicationOperation(OperationBase):

    _input_parameters = {
                         ParameterName.AwsAccessKeyId, 
                         ParameterName.AwsSecretAccessKey,
                         ParameterName.ServiceEndpoint, 
                         ParameterName.ApplicationName,
                        }
    
    _output_parameters = set()

    
    def execute(self, parameter_pool):
        eb_client = ElasticBeanstalkClient(parameter_pool.get_value(ParameterName.AwsAccessKeyId), 
                                           parameter_pool.get_value(ParameterName.AwsSecretAccessKey),
                                           parameter_pool.get_value(ParameterName.ServiceEndpoint))

        app_name = parameter_pool.get_value(ParameterName.ApplicationName)
        env_name = parameter_pool.get_value(ParameterName.EnvironmentName)
        prompt.action(DeleteApplicationOpMessage.Start.format(app_name))

        try:
            response = eb_client.delete_application(app_name, 'true')
        except OperationInProgressException:
            log.info('Deleting Application "{0}" already in progress'.format(app_name))
            prompt.result(DeleteApplicationOpMessage.AlreadyDelete.format(app_name))
   
            ret_result = OperationResult(self,
                                         None, 
                                         DeleteApplicationOpMessage.AlreadyDelete.format(app_name),
                                         None)
        else:
            log.info('Received response for DeleteApplication call.')
            self._log_api_result(self.__class__.__name__, 'DeleteApplication', response.result)            
            prompt.result(DeleteApplicationOpMessage.Succeed.format(app_name))
    
            credential_file_loc = config_file.default_aws_credential_file_location()
            param_list = [rds_utils.password_key_name(env_name)]
            config_file.trim_aws_credential_file(credential_file_loc, parameter_pool, param_list, True)
    
            ret_result = OperationResult(self,
                                         response.request_id, 
                                         DeleteApplicationOpMessage.Succeed.format(app_name),
                                         response.result)

        
            
        return ret_result
        
