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

import re as _re

from lib.utility import misc
from scli import api_wrapper
from scli.constants import ParameterSource
from scli.constants import ParameterName
from scli.constants import ServiceDefault
from scli.terminal.base import TerminalBase
from scli.resources import TerminalMessage
from scli.resources import TerminalPromptAskingMessage
from scli.resources import TerminalPromptSettingParameterMessage
from scli.parameter import Parameter


class BeanstalkTerminal(TerminalBase):

    @classmethod
    def ask_application_name(cls, parameter_pool):
        if not parameter_pool.has(ParameterName.ApplicationName):
            app_name = misc.get_current_dir_name()
            cls.ask_parameter(parameter_pool, 
                               ParameterName.ApplicationName,
                               autogen_value = app_name)
        else:
            cls.ask_parameter(parameter_pool, ParameterName.ApplicationName)            
        

    @classmethod
    def ask_environment_name(cls, parameter_pool):
        #Auto generate environment name if not specified by user
        if not parameter_pool.has(ParameterName.EnvironmentName):
            app_name = parameter_pool.get_value(ParameterName.ApplicationName)
            env_name = _re.sub(ServiceDefault.Environment.REGEX_NAME_FILTER, 
                               u'', app_name, flags = _re.UNICODE)
            if len(env_name) > 0:
                env_name = env_name + ServiceDefault.Environment.NAME_POSTFIX
                if len(env_name) > ServiceDefault.Environment.MAX_NAME_LEN:
                    env_name = env_name[:ServiceDefault.Environment.MAX_NAME_LEN]
            else:
                env_name = None
            cls.ask_parameter(parameter_pool, 
                               ParameterName.EnvironmentName,
                               autogen_value = env_name)
        else:
            cls.ask_parameter(parameter_pool, ParameterName.EnvironmentName)            
    

    @classmethod
    def ask_solution_stack(cls, parameter_pool):
        
        # Skip if user supplies solution stack string as CLI arguments, or already by terminal
        if parameter_pool.has(ParameterName.SolutionStack) \
            and ParameterSource.is_ahead(parameter_pool.get_source(ParameterName.SolutionStack),
                                         ParameterSource.ConfigFile):
            print(TerminalPromptSettingParameterMessage[ParameterName.SolutionStack].\
                  format(parameter_pool.get_value(ParameterName.SolutionStack)))
            return            
        
        original_value = parameter_pool.get_value(ParameterName.SolutionStack) \
            if parameter_pool.has(ParameterName.SolutionStack) else None
        append_message = u'' if original_value is None \
            else TerminalMessage.CurrentValue.format(original_value)        
        print(TerminalPromptAskingMessage[ParameterName.SolutionStack].\
              format(append_message))
        
        stacks = api_wrapper.retrieve_solution_stacks(parameter_pool)
        stack_index = cls.single_choice(stacks, 
                                        TerminalMessage.AvailableSolutionStack, None,
                                        original_value is not None)
        
        value = stacks[stack_index] if stack_index is not None else original_value
        stack = Parameter(ParameterName.SolutionStack, value, ParameterSource.Terminal)
        parameter_pool.put(stack, True)

