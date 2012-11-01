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
import os
import locale
import logging as _logging
import subprocess as _subprocess

from scli import config_file
from scli import prompt
from scli import api_wrapper
from scli.constants import AwsCredentialFileDefault, RdsDefault
from scli.constants import ParameterName
from scli.constants import ParameterSource
from scli.constants import EbConfigFile
from scli.constants import EbLocalDir
from scli.constants import FileErrorConstant
from scli.constants import GitIgnoreFile
from scli.constants import DevToolsConfigFile
from scli.constants import OSSpecific
from scli.constants import ServiceRegionId
from scli.exception import EBSCliException
from scli.exception import EBConfigFileNotExistError
from scli.operation.base import OperationBase
from scli.operation.base import OperationResult
from scli.parameter import Parameter
from scli.resources import CommandType
from scli.resources import ConfigFileMessage
from scli.resources import ConfigFileErrorMessage
from scli.resources import DevToolsMessage
from scli.resources import SaveConfigurationSettingOpMessage
from scli.resources import WriteAwsCredentialFileOpMessage
from lib.utility import misc

log = _logging.getLogger('cli.op')


def create_eb_local_dir():
    config_file.create_directory(os.getcwd() + os.path.sep + EbLocalDir.Path)    

# Format: ParameterName, from_file function, to_file function
CredentialFileParameters = [
    (ParameterName.AwsAccessKeyId, None, None), 
    (ParameterName.AwsSecretAccessKey, None, None), 
    (ParameterName.RdsMasterPassword, None, None), 
]


class ReadAwsCredentialFileOperation(OperationBase):
    '''
    Try to read AWS credential ID and key from AWS_CREDENTIAL_FILE specified by user 
    or stored in local OS environment variables
    '''  
    _input_parameters = set()
    _output_parameters = set()
    
    def execute(self, parameter_pool):
        # Try to retrieve all credential info from specified file        
        file_param = parameter_pool.get(ParameterName.AwsCredentialFile) \
            if parameter_pool.has(ParameterName.AwsCredentialFile) else None
        if file_param is not None:
            self._try_read_credential_file(parameter_pool, 
                                           file_param.value, 
                                           file_param.source)
        else:
            location = config_file.default_aws_credential_file_location()        
            self._try_read_credential_file(parameter_pool, 
                                           location, 
                                           ParameterSource.ConfigFile)


        
        osenv_location =  os.getenv(AwsCredentialFileDefault.OSVariableName)
        if osenv_location is not None:
            self._try_read_credential_file(parameter_pool, 
                                           osenv_location, 
                                           ParameterSource.OsEnvironment)

        ret_result = OperationResult(self, None, None, None)
        return ret_result


    def _try_read_credential_file(self, parameter_pool, location, source):
        func_matrix = []
        for param in CredentialFileParameters:
            if not parameter_pool.has(param[0]):
                func_matrix.append((param[0], param[1]))
        config_file.read_aws_credential_file(location, parameter_pool, 
                                             func_matrix, source, True)


class UpdateAwsCredentialFileOperation(OperationBase):
    '''
    Generate AWS credential file if it is not retrieved from local OS environment variables
    '''  
    _input_parameters = {
                         ParameterName.AwsAccessKeyId, 
                         ParameterName.AwsSecretAccessKey,
                         }
    
    _output_parameters = set()
        
    def execute(self, parameter_pool):
        
        func_matrix = []        
        for param in CredentialFileParameters:
            if not parameter_pool.has(param[0]):
                continue
            elif ParameterSource.is_ahead(ParameterSource.Terminal,\
                                        parameter_pool.get_source(param[0])):
                continue
            else:
                func_matrix.append((param[0], param[2]))
        
        if len(func_matrix) < 1:
            log.info('Skipped updating credential file as credentials are not changed.')
            return 

        location = config_file.default_aws_credential_file_location()        
        # Create directory if needed
        try:
            config_file.create_directory(config_file.default_aws_credential_file_path())
            config_file.write_aws_credential_file(location, parameter_pool, func_matrix)
        except BaseException as ex:
            log.error('Encountered error when creating AWS Credential file at "{0}", because {1}.'.\
                      format(location, ex))
            return
        
        else:
            log.info(WriteAwsCredentialFileOpMessage.Succeed.format(location))
            prompt.result(WriteAwsCredentialFileOpMessage.Succeed.format(location))
            
            parameter_pool.put(Parameter(ParameterName.AwsCredentialFile,
                                         location,
                                         ParameterSource.OperationOutput),
                               True)
            
            ret_result = OperationResult(self, None, None, None)
            return ret_result


class LoadEbConfigFileOperation(OperationBase):
    _input_parameters = set()
    _output_parameters = set()
    
    def execute(self, parameter_pool):
        location = EbLocalDir.Path + os.path.sep + EbConfigFile.Name
        
        try:
            config_file.load_eb_config_file(location, parameter_pool, False)
            if config_file.check_access_permission(location) is False:
                message = ConfigFileErrorMessage.PermissionError.format(EbConfigFile.Name)
                log.info(message)
                prompt.error(message)
           
            #Post processing
            if not parameter_pool.has(ParameterName.RdsSnippetUrl)\
                and parameter_pool.has(ParameterName.Region):
                region = parameter_pool.get_value(ParameterName.Region)
                parameter_pool.put(Parameter(ParameterName.RdsSnippetUrl,
                                             RdsDefault.get_snippet_url(region),
                                             ParameterSource.ConfigFile))
            
        except EBConfigFileNotExistError:
            log.error('Configuration file "{0}" not exist.'.format(EbConfigFile.Name))
            prompt.error(ConfigFileMessage.CannotFind.format\
                        (EbConfigFile.Name, CommandType.INIT.lower()))
            raise EBSCliException()
            
        except BaseException as ex:
            log.error('Encountered error when load configuration file "{0}", becuase "{1}".'.\
                      format(EbConfigFile.Name, ex))
            prompt.error(ConfigFileMessage.CorrectionSuggestion.
                         format(location,CommandType.INIT.lower()))
            raise

        ret_result = OperationResult(self, None, None, None)
        return ret_result

    
class TryLoadEbConfigFileOperation(OperationBase):
    _input_parameters = set()
    _output_parameters = set()
    
    def execute(self, parameter_pool):
        location = EbLocalDir.Path + os.path.sep + EbConfigFile.Name
        
        config_file.load_eb_config_file(location, parameter_pool, True)

        ret_result = OperationResult(self, None, None, None)
        return ret_result



class SaveEbConfigFileOperation(OperationBase):
    _input_parameters = set()
    _output_parameters = set()
    
    def execute(self, parameter_pool):
        create_eb_local_dir()
        
        location = EbLocalDir.Path + os.path.sep + EbConfigFile.Name
        
        config_file.save_eb_config_file(location, parameter_pool, False)
        config_file.set_access_permission(location)
        
        ret_result = OperationResult(self, None, None, None)
        return ret_result
    

class UpdateDevToolsConfigOperation(OperationBase):

    _input_parameters = set()
    _output_parameters = set()
    
    def execute(self, pool):
        
        # Test if git local repo exists
        if not os.path.isdir(os.path.join(os.getcwd(), DevToolsConfigFile.Path)):
            prompt.error(DevToolsMessage.GitRepoNotExist.format(CommandType.INIT.lower()))
#            raise EBSCliException()
            return
        
        region_id = ServiceRegionId[pool.get_value(ParameterName.Region)]
        try:
            self.run_dev_tools_script()
            
            self._call(DevToolsConfigFile.SetAccessKey, 
                       pool.get_value(ParameterName.AwsAccessKeyId))
            self._call(DevToolsConfigFile.SetSecretKey, 
                       pool.get_value(ParameterName.AwsSecretAccessKey))
            self._call(DevToolsConfigFile.SetRegion, 
                       region_id)
            self._call(DevToolsConfigFile.SetServicePoint, 
                       DevToolsConfigFile.Endpoint.format(region_id))
            self._call(DevToolsConfigFile.SetApplicationName, 
                       pool.get_value(ParameterName.ApplicationName))
            self._call(DevToolsConfigFile.SetEnvironmentName, 
                       pool.get_value(ParameterName.EnvironmentName))
            
            location = DevToolsConfigFile.Path + os.path.sep + DevToolsConfigFile.Name        
            config_file.set_access_permission(location, True)
            
        except (OSError, IOError, _subprocess.CalledProcessError) as ex:
            log.error("Encountered error when updating AWS Dev Tools settings: {0}.".format(ex))
            message = DevToolsMessage.ExecutionError.format(DevToolsConfigFile.InitHelpUrl)
            prompt.error(message)
#            raise EBSCliException()
        
        ret_result = OperationResult(self, None, None, None)
        return ret_result
    
    
    def _call(self, command, *params):
        '''
        Call external process. command is a list of command line arguments including name
        of external process. params will be appended at the tail of command.
        '''
        if not isinstance(command, list):
            raise EBSCliException('Parameter must be instance of list.')
        command_line = command
        for param in params:
            command_line.append(param)
        
        log.debug('Running external commands "{0}".'.\
                  format(misc.collection_to_string(command_line)))    
        if misc.is_os_windows():
            # TODO: set shell to True will allow Windows translate "git" to "git.cmd", 
            # but might introduce other issues.
            # Using Windows native code page 
            command_line = [x.encode(locale.getpreferredencoding()) for x in command_line]        
            return _subprocess.check_output(command_line, shell=True)
        else:
            return _subprocess.check_output(command_line)


    def run_dev_tools_script(self):

        log.info('Running Dev Tools initialization script.')
        current_path = os.getcwd()
        
        try:
            if misc.is_os_windows():
                path = self._climb_dir_tree(misc.ori_path(), OSSpecific.WindowsClimbUpDepth)
                #TODO: replace current workaround for WindowsModuleScript
                current_path = os.getcwd()
                script_path = os.path.join(path, OSSpecific.WindowsModuleScriptPath)
                log.debug('Changing path to {0}.'.format(script_path))
                os.chdir(script_path)

                log.info('Running script "{0}".'.format(OSSpecific.WindowsModuleScriptName))
                self._call([OSSpecific.WindowsModuleScriptName])
                
                log.debug('Changing path to {0}.'.format(current_path))
                os.chdir(current_path)
                
                log.info('Running script "{0}".'.format(OSSpecific.WindowsRepoScript))
                self._call([os.path.join(path, OSSpecific.WindowsRepoScript)])
            else:
                path = self._climb_dir_tree(misc.ori_path(), OSSpecific.LinuxClimbUpDepth)
                log.info('Running script "{0}" at {1}.'.format(OSSpecific.LinuxRepoScript,
                                                                path))
                self._call([os.path.join(path, OSSpecific.LinuxRepoScript)])
                
        except _subprocess.CalledProcessError as ex:
            # Git returned with an error code
            log.error('Dev Tools initialiation script report an error, because "{0}".'.format(ex))
            prompt.error(DevToolsMessage.InitError)
            raise
        
        except (OSError, IOError) as ex:
            log.error('Failed to call Dev Tools initialiation script, because "{0}".'.format(ex))
            # Cannot find or run script
            if ex.errno == FileErrorConstant.FileNotFoundErrorCode:
                prompt.error(DevToolsMessage.FileMissingError)
            raise
        

    def _climb_dir_tree(self, path, level):
        target_path = path
        for _ in range(level):
            target_path = os.path.dirname(target_path)
        return target_path


class CheckGitIgnoreFileOperation(OperationBase):

    _input_parameters = set()
    
    _output_parameters = set()

    def execute(self, pool):
        location = GitIgnoreFile.Path + os.path.sep + GitIgnoreFile.Name        
        config_file.add_ignore_file(location)
        
        ret_result = OperationResult(self, None, None, None)
        return ret_result        




class SaveConfigurationSettingOperation(OperationBase):
    _input_parameters = {
                         ParameterName.AwsAccessKeyId, 
                         ParameterName.AwsSecretAccessKey,
                         ParameterName.ServiceEndpoint, 
                         ParameterName.ApplicationName,
                         ParameterName.EnvironmentName,
                         ParameterName.OptionSettingFile,
                        }
    
    _output_parameters = set()
    
    def execute(self, parameter_pool):
        create_eb_local_dir()

        app_name = parameter_pool.get_value(ParameterName.ApplicationName)
        env_name = parameter_pool.get_value(ParameterName.EnvironmentName)
        location = parameter_pool.get_value(ParameterName.OptionSettingFile)            

        prompt.action(SaveConfigurationSettingOpMessage.Start.format(env_name))
        
        try:
            option_settings = api_wrapper.retrieve_configuration_settings(parameter_pool,
                                                                          app_name,
                                                                          env_name)
            config_file.save_env_option_setting_file(location, option_settings)
        except Exception as ex:
            # Never fail. Just log event if any exception
            log.info('Cannot dump environment option settings before termination, because '.\
                     format(misc.to_unicode(ex)))
            option_settings = None
        else:
            log.info(SaveConfigurationSettingOpMessage.Succeed.format(location))
            prompt.info(SaveConfigurationSettingOpMessage.Succeed.format(location))
                   
        ret_result = OperationResult(self,
                                     None, 
                                     None,
                                     option_settings)
        return ret_result



class RotateOptionsettingFileOperation(OperationBase):
    _input_parameters = {
                         ParameterName.OptionSettingFile,
                        }
    
    _output_parameters = set()
    
    def execute(self, parameter_pool):
        ori_stack = parameter_pool.get_value(ParameterName.OriginalSolutionStack)\
            if parameter_pool.has(ParameterName.OriginalSolutionStack) else None
        stack = parameter_pool.get_value(ParameterName.SolutionStack)\
            if parameter_pool.has(ParameterName.SolutionStack) else None
        
        if ori_stack is None or ori_stack == stack:
            log.info('Solution stack is not changed. Keeping current optionsettings file.')
        else:
            log.info('Rotate optionsettings file becuase solution stack is changed.')
            location = parameter_pool.get_value(ParameterName.OptionSettingFile)            
            config_file.rotate_file(location)
        
        ret_result = OperationResult(self, None, None, None)
        return ret_result
    
    
    