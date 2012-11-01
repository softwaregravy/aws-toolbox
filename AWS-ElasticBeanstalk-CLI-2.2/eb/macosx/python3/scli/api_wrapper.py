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
from collections import deque as _deque

from lib.elasticbeanstalk.servicecall import ElasticBeanstalkClient
from lib.elasticbeanstalk.exception import AlreadyExistException
from lib.rds.servicecall import RdsClient
from lib.utility import misc
from scli.constants import ParameterName

log = _logging.getLogger('cli')


def log_response(api_name, result):
    if log.isEnabledFor(_logging.DEBUG):
        log.debug('{0} response: {1}'.\
                  format(api_name, misc.collection_to_string(result)))


#---------------------------------------------
# Elastic Beanstalk API wrappers
#---------------------------------------------

def create_eb_client(parameter_pool):
    endpoint = parameter_pool.get_value(ParameterName.ServiceEndpoint)

    eb_client = ElasticBeanstalkClient(parameter_pool.get_value(ParameterName.AwsAccessKeyId), 
                                       parameter_pool.get_value(ParameterName.AwsSecretAccessKey),
                                       endpoint)

    log.info('Create EB client to talk to {0}.'.format(endpoint))

    return eb_client


def retrieve_solution_stacks(parameter_pool, eb_client = None):
    if eb_client is None:
        eb_client = create_eb_client(parameter_pool)

    log.info('Send request for ListAvailableSolutionStack call.')
    response = eb_client.list_available_solutionstacks()
    log.info('Received response for ListAvailableSolutionStack call.')
    log_response('ListAvailableSolutionStack', response.result)            
    
    stack_list = list()
    for stack in response.result:
        stack_list.append(stack.solutionstack_name)
    
    return stack_list


def retrieve_environment_resources(parameter_pool, env_name = None, eb_client = None):
    if eb_client is None:
        eb_client = create_eb_client(parameter_pool)

    log.info('Send request for DescribeEnvironments call.')
    response = eb_client.describe_environment_resources(env_name)
    log.info('Received response for DescribeEnvironments call.')
    log_response('DescribeEnvironments', response.result)            

    return response.result


def retrieve_configuration_settings(parameter_pool, app_name, 
                                    env_name = None, template = None, 
                                    options = None, eb_client = None):
    if eb_client is None:
        eb_client = create_eb_client(parameter_pool)
        
    log.info('Send request for DescribeConfigurationSettings call.')
    response = eb_client.describe_configuration_settings(app_name,
                                                         environment_name = env_name,
                                                         template = template,
                                                         options = options)
    log.info('Received response for DescribeConfigurationSettings call.')
    log_response('DescribeConfigurationSettings', response.result)            
    
    return response.result.option_settings


def retrieve_configuration_options(parameter_pool, 
                                   app_name = None, env_name = None, 
                                   template = None, solution_stack = None,
                                   options = None, eb_client = None):
    if eb_client is None:
        eb_client = create_eb_client(parameter_pool)

    log.info('Send request for DescribeConfigurationOptions call.')
    response = eb_client.describe_configuration_options(application_name = app_name, 
                                                        environment_name = env_name, 
                                                        template = template, 
                                                        solution_stack = solution_stack, 
                                                        options = options)
    log.info('Received response for DescribeConfigurationOptions call.')
    log_response('DescribeConfigurationOptions', response.result)            
    
    return response.result



def create_application(parameter_pool, app_name, eb_client = None):
    if eb_client is None:
        eb_client = create_eb_client(parameter_pool)
    try:
        log.info('Send request for CreateApplication call.')
        eb_client.create_application(app_name)
        log.info('Received response for CreateApplication call.')
    except AlreadyExistException:
        log.info('Application "{0}" already exists.'.format(app_name))
    else:
        log.info('Created Application "{0}".'.format(app_name))
    


#---------------------------------------------
# RDS API wrappers
#---------------------------------------------

def create_rds_client(parameter_pool):
    rds_endpoint = parameter_pool.get_value(ParameterName.RdsEndpoint)

    rds_client = RdsClient(parameter_pool.get_value(ParameterName.AwsAccessKeyId), 
                           parameter_pool.get_value(ParameterName.AwsSecretAccessKey),
                           rds_endpoint)

    log.info('Create RDS client to talk to {0}.'.format(rds_client))

    return rds_client

def retrive_rds_instance(parameter_pool, instance_id):
    rds_client = create_rds_client(parameter_pool)
    
    response = rds_client.describe_db_instances(instance_id)
    log.info('Received response for DescribeDBInstances call.')
    log_response('DescribeDBInstances', response.result)            
    
    if not isinstance(response.result, list):
        return list(response.result)
    else:
        return response.result[0]


def retrive_rds_snapshots(parameter_pool):
    rds_client = create_rds_client(parameter_pool)
    
    response = rds_client.describe_db_snapshots()
    log.info('Received response for DescribeDBSnapshots call.')
    log_response('DescribeDBSnapshots', response.result)            
    
    if not isinstance(response.result, list):
        return list(response.result)
    else:
        return response.result


def retrive_rds_engine_versions(parameter_pool):
    rds_client = create_rds_client(parameter_pool)
    
    response = rds_client.describe_db_engine_versions()
    log.info('Received response for DescribeDBEngineVersions call.')
    log_response('DescribeDBEngineVersions', response.result)            
    
    if not isinstance(response.result, list):
        return list(response.result)
    else:
        return response.result


def retrive_rds_engines(parameter_pool):
    engine_versions = retrive_rds_engine_versions(parameter_pool)
    
    db_engines = _deque()
    for engine_version in engine_versions:
        if engine_version.engine not in db_engines:
            db_engines.append(engine_version.engine)

    return list(db_engines)


def retrive_rds_default_engine_versions(parameter_pool):
    
    db_engines = retrive_rds_engines(parameter_pool)
    rds_client = create_rds_client(parameter_pool)

    db_default_versions = _deque()
    for engine in db_engines:
        response = rds_client.describe_db_engine_versions(engine = engine,
                                                          default_only = 'true')
        log.info('Received response for DescribeDBEngineVersions call.')
        log_response('DescribeDBEngineVersions', response.result)            
        db_default_versions.append(response.result[0])
    
    return list(db_default_versions)
