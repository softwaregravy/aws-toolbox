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
from scli.constants import KnownAppContainers

from lib.elasticbeanstalk.model import OptionSepcification
from lib.utility import misc
from scli import api_wrapper
from scli.constants import DefualtAppSource
from scli.constants import OptionSettingVPC

def match_solution_stack(solution_stack):
    for container in KnownAppContainers:
        if _re.match(container.Regex, solution_stack, _re.UNICODE):
            return container.Name
    return None



def has_default_app(parameter_pool, solution_stack, eb_client = None):
    appsource = OptionSepcification(DefualtAppSource.Namespace, DefualtAppSource.OptionName)
    
    options = api_wrapper.retrieve_configuration_options(parameter_pool, 
                                            solution_stack = solution_stack,
                                            options = [appsource],
                                            eb_client = eb_client)
    for option in options:
        if misc.string_equal_ignore_case(DefualtAppSource.Namespace, option.namespace) \
            and misc.string_equal_ignore_case(DefualtAppSource.OptionName, option.name):
            return True
        
    return False

def trim_vpc_options(option_settings, option_to_remove):
    trim = False
    vpc_options = set();
    for option in option_settings:
        if option.namespace ==  OptionSettingVPC.Namespace:
            vpc_options.add(option)
            if option.option_name == OptionSettingVPC.MagicOptionName\
                and (option.value is None or len(option.value) < 1):
                trim = True
    if trim:
        for option in vpc_options:
            option_settings.remove(option)
            
        
                
        
    
