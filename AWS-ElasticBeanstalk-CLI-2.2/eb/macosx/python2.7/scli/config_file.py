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
import os as _os
import re as _re
import stat as _stat

from scli import prompt
from scli.constants import AwsCredentialFileDefault
from scli.constants import FileDefaultParameter
from scli.constants import FileErrorConstant
from scli.constants import GitIgnoreFile
from scli.constants import LocalOptionSettings
from scli.constants import OptionSettingContainerPrefix
from scli.constants import OptionSettingApplicationEnvironment
from scli.constants import RdsDefault
from scli.constants import ParameterName
from scli.constants import ParameterSource
from scli.constants import ServiceRegionId
from scli.exception import EBSCliException
from scli.exception import EBConfigFileNotExistError
from scli.parameter import Parameter
from scli.resources import CredentialFileErrorMessage
from scli.resources import ConfigFileErrorMessage
from scli.resources import GeneralFileMessage
from scli.resources import OptionSettingFileErrorMessage
from lib.elasticbeanstalk.model import ConfigurationOptionSetting
from lib.rds import rds_utils
from lib.utility.configfile_parser import NoSectionConfigParser 
from lib.utility.configfile_parser import SectionedConfigParser
from lib.utility import misc

log = _logging.getLogger('cli')


#------------------------------
# Helper
#------------------------------

def create_directory(directory):
    ''' Create a directory at location. Return if exist. '''                    
    if not _os.path.exists(directory):
        _os.makedirs(directory)
    
    
def rotate_file(location, max_retry = FileDefaultParameter.RotationMaxRetry):
    ''' Rotate a file by adding a incremental postfix to filename'''
    if not _os.path.exists(location):
        return
     
    filename = _os.path.basename(location)
    path = _os.path.dirname(location)
    for i in range(1, max_retry):
        new_location = _os.path.join(path, (filename + u'_{0}'.format(i)))
        if not _os.path.exists(new_location):
            log.info(u'Renamed file "{0}" to "{1}".'.format(location, new_location))
            prompt.info(GeneralFileMessage.RenameFile.format(location, new_location))
            _os.rename(location, new_location)
            return
    else:
        log.error(u'Cannot rotate file {0} because all available names are used.'.\
                  format(location))
        prompt.error(GeneralFileMessage.RotationNameNotAvailable.format(location))
        return
    

#------------------------------
# File access permission
#------------------------------
def check_access_permission(location, quiet = False):
    log.info(u'Checking file access permission at "{0}".'.format(location))
    if misc.is_os_windows(): 
        log.debug(u'Skipped checking file access permission for Windows platform.')
        return None

    try:
        file_mode = _os.stat(location).st_mode
        if 0 != _stat.S_IMODE(file_mode) & _stat.S_IRWXG or\
            0 != _stat.S_IMODE(file_mode) & _stat.S_IRWXO :
            return False
        return True
    except BaseException as ex:
        log.error(u'Encountered error when checking access permission for file "{0}", because "{1}".'.\
                  format(location, ex))
        if quiet:
            return None
        else:
            raise


def set_access_permission(location, quiet = False):
    log.info(u'Setting file access permission at "{0}".'.format(location))
    if misc.is_os_windows():
        log.debug(u'Skipped setting file access permission for Windows platform.')
        return False

    try:
        _os.chmod(location, _stat.S_IRUSR | _stat.S_IWUSR)
        return True
    except BaseException as ex:
        log.error(u'Encountered error when setting access permission for file "{0}", because "{1}".'.\
                  format(location, ex))
        if quiet:
            return False
        else:
            raise


#------------------------------
# Git ignore file
#------------------------------
def add_ignore_file(location):
    '''
    Add EB config files and log files to git ignore file
    '''
    log.info(u'Adding ignore files to "{0}".'.format(location))
    # Compile ignore file dict and regular expressions
    namelist = dict()
    relist = dict()
    for item in GitIgnoreFile.Files:
        namelist[item.Name] = True
        relist[item.Name] = _re.compile(item.NameRe, _re.UNICODE)
    log.debug(u'Files needs to present in git ignore list: {0}'.\
              format(misc.collection_to_string(namelist.keys())))

    with open(location, 'a+') as f:
        # Search for filenames
        f.seek(0, _os.SEEK_SET)
        for line in f:
            for name, re in relist.items():
                if re.match(line):
                    namelist[name] = False
        
        # Add filenames if not present in ignore file
        f.seek(0, _os.SEEK_END)
        for name, add in namelist.items():
            if add:
                log.debug(u'Adding file "{0}" to git ignore list.'.format(name))
                f.write(u'{0}'.format(name))
  

#------------------------------
# Credential File
#------------------------------

def default_aws_credential_file_path():
    # Get home folder of current user
    return _os.path.join(_os.path.expanduser('~'), AwsCredentialFileDefault.FilePath)

def default_aws_credential_file_location():
    return _os.path.join(default_aws_credential_file_path(), AwsCredentialFileDefault.FileName)        


def read_aws_credential_file(location, parameter_pool, func_matrix, source, quiet = False):
    try:
        env_name = parameter_pool.get_value(ParameterName.EnvironmentName) \
            if parameter_pool.has(ParameterName.EnvironmentName) else u''
        
        log.info(u'Reading AWS credential from file: "{0}"'.format(location))
        parser = NoSectionConfigParser()
        parser.read(location)

        for name, from_file_func in func_matrix:
            if name == ParameterName.RdsMasterPassword:
                key_name = rds_utils.password_key_name(env_name)
            else:
                key_name = AwsCredentialFileDefault.KeyName[name]
                
            if parser.has_option(key_name):
                value = parser.get(key_name)
                value = from_file_func(value) if from_file_func is not None else value
                parameter_pool.put(Parameter(name, value, source))
        log.info(u'Finished reading AWS credential from file.')
                
    except BaseException as ex:
        log.error(u'Failed to retrieve AWS credential from file "{0}", because: "{1}"'.\
                  format(location, ex))
        if not quiet:
            msg = CredentialFileErrorMessage.ReadError.format(location)
            prompt.error(msg)
            raise EBSCliException(msg)
        else:          
            return False # if failed, just skip 
    

def write_aws_credential_file(location, parameter_pool, 
                              func_matrix,
                              quiet = False):
    try:
        env_name = parameter_pool.get_value(ParameterName.EnvironmentName) \
            if parameter_pool.has(ParameterName.EnvironmentName) else u''        
        
        log.info(u'Writing AWS credential to file: "{0}"'.format(location))
        parser = NoSectionConfigParser()
        try:
            parser.read(location)
        except IOError as ex:
            pass # No existing file
        
        for name, to_file_func in func_matrix:
            param = parameter_pool.get(name)
            value = to_file_func(param.value) if to_file_func is not None else param.value

            if name == ParameterName.RdsMasterPassword:
                key_name = rds_utils.password_key_name(env_name)
            else:
                key_name = AwsCredentialFileDefault.KeyName[name]
            parser.set(key_name, value)
        
        parser.write(location)
        log.info(u'Finished writing AWS credential to file.')
                
        # Set access permission
        set_access_permission(location, False)
        log.info(u'Set AWS credential file access permission.')
        
    except BaseException as ex:
        log.error(u'Failed to update AWS credential file at "{0}", because: "{1}"'.\
                  format(location, ex))
        msg = CredentialFileErrorMessage.WriteError.format(location)
        prompt.error(msg)
        if not quiet:
            raise EBSCliException(msg)
        else:          
            return False # if failed, just skip 


def trim_aws_credential_file(location, parameter_pool, 
                             param_list,
                             quiet = False):
    try:
        log.info(u'Trimming AWS credential file: "{0}"'.format(location))
        parser = NoSectionConfigParser()
        try:
            parser.read(location)
        except IOError as ex:
            return # File not exists
        
        for name in param_list:
            parser.remove_option(name)
        
        parser.write(location)
        log.info(u'Finished trimming AWS credential file.')
                
        # Set access permission
        set_access_permission(location, False)
        log.info(u'Set AWS credential file access permission.')
        
    except BaseException as ex:
        log.error(u'Failed to trim AWS credential file at "{0}", because: "{1}"'.\
                  format(location, ex))
        msg = CredentialFileErrorMessage.WriteError.format(location)
        prompt.error(msg)
        if not quiet:
            raise EBSCliException(msg)
        else:          
            return False # if failed, just skip 
        
        
#------------------------------
# Config File
#------------------------------

def _region_id_to_region(region_id):
    return ServiceRegionId.keys()[ServiceRegionId.values().index(region_id)]

def _region_to_region_id(region):
    return ServiceRegionId[region]

def _none_to_empty_string(value):
    if value is None:
        return u''
    else:
        return value

def _empty_string_to_none(value):
    if value == u'' or len(value) < 1:
        return None
    else:
        return value


# Format: ParameterName, from_file function, to_file function
ConfigFileParameters = [
    (ParameterName.AwsCredentialFile, None, None), 
    (ParameterName.ApplicationName, None, None), 
    (ParameterName.EnvironmentName, None, None), 
    (ParameterName.Region, _region_id_to_region, _region_to_region_id), 
    (ParameterName.ServiceEndpoint, None, None), 
    (ParameterName.RdsEndpoint, None, None), 
    (ParameterName.SolutionStack, None, None), 
    (ParameterName.RdsEnabled, misc.string_to_boolean, misc.bool_to_yesno), 
    (ParameterName.RdsSourceSnapshotName, _empty_string_to_none, _none_to_empty_string), 
    (ParameterName.RdsDeletionPolicy, None, None), 
]


def load_eb_config_file(location, parameter_pool, quiet = False):
    try:
        log.info(u'Reading EB configuration from file: "{0}"'.format(location))
        parser = NoSectionConfigParser()
        parser.read(location)

        for (name, from_file, _) in ConfigFileParameters:
            if parser.has_option(name):
                value = parser.get(name)
                if from_file is not None:
                    value = from_file(value)
                parameter_pool.put(Parameter(name, value, ParameterSource.ConfigFile))

        # Add original solution stack infos
        if parser.has_option(ParameterName.SolutionStack):
            parameter_pool.put(Parameter(ParameterName.OriginalSolutionStack, 
                                         parser.get(ParameterName.SolutionStack), 
                                         ParameterSource.ConfigFile))
            

        log.info(u'Finished reading from EB configuration file.')
        
    except BaseException as ex:
        log.error(u'Failed to parse EB configuration from file, because: "{0}"'.format(ex))
        if not quiet:
            if (isinstance(ex, OSError) or isinstance(ex, IOError)) and\
                ex.errno == FileErrorConstant.FileNotFoundErrorCode:
                raise EBConfigFileNotExistError(ex)
            else:
                msg = ConfigFileErrorMessage.ReadError.format(location)
                prompt.error(msg)
                raise EBConfigFileNotExistError(msg)
        else:    
            pass # if failed, just skip     

        
def save_eb_config_file(location, parameter_pool, quiet = False):
    try:
        log.info(u'Writing EB configuration to file: "{0}"'.format(location))
        parser = NoSectionConfigParser()

        for (name, _, to_file) in ConfigFileParameters:
            if parameter_pool.has(name):
                value = parameter_pool.get_value(name)
                if to_file is not None:
                    value = to_file(value)
                parser.set(name, value)

        parser.write(location)
        log.info(u'Finished writing EB configuration file.')
        
    except BaseException as ex:
        log.error(u'Failed to save EB configuration file, because: "{0}"'.format(ex))
        prompt.error(ConfigFileErrorMessage.WriteError.format(location))        
        raise
    

          
            
#------------------------------
# Option Setting File
#------------------------------

def load_env_option_setting_file(location, option_settings = None, quiet = False):
    log.info(u'Reading environment option settings from file at "{0}".'.format(location))
    
    if option_settings is None:
        option_settings = []
    
    try:
        parser = SectionedConfigParser()
        parser.read(location)
        
        for section in parser.sections():
            for option, value in parser.items(section):
                cos = ConfigurationOptionSetting()
                cos._namespace = misc.to_unicode(section)
                cos._option_name = misc.to_unicode(option)
                cos._value = misc.to_unicode(value)
                option_settings.append(cos) 
        
        log.debug(u'Option settings read from file include: "{0}".'.\
                  format(misc.collection_to_string(option_settings)))
        
        check_access_permission(location, True)
        return option_settings
    
    except BaseException as ex:
        log.error(u'Failed to load environment option setting file, because: "{0}"'.format(ex))
        if quiet:
            return []
        else:
            prompt.error(OptionSettingFileErrorMessage.ReadError.format(location))        
            raise

            
def save_env_option_setting_file(location, option_settings):
    log.info(u'Writing environment option settings to file at "{0}".'.format(location))
    try:
        parser = SectionedConfigParser()
        
        for setting in option_settings:
            
            if setting.namespace.startswith(OptionSettingContainerPrefix):
                pass
            elif setting.namespace.startswith(OptionSettingApplicationEnvironment.Namespace):
                if setting.option_name in OptionSettingApplicationEnvironment.IgnoreOptionNames:
                    continue
                else:
                    pass
            # Skip if option setting is on in local option setting list
            elif setting.namespace not in LocalOptionSettings \
                or setting.option_name not in LocalOptionSettings[setting.namespace]:
                continue
            
            if not parser.has_section(setting.namespace):
                parser.add_section(setting.namespace)
                
            if setting.value is None:
                setting._value = u''
            parser.set(setting.namespace, setting.option_name, setting.value)
        
        parser.write(location)
        log.debug(u'Option settings written to file include: "{0}".'.\
                  format(misc.collection_to_string(option_settings)))
       
        set_access_permission(location, True)
    except BaseException as ex:
        log.error(u'Failed to save environment option setting file, because: "{0}"'.format(ex))
        prompt.error(OptionSettingFileErrorMessage.WriteError.format(location))        
        raise
    
    
        