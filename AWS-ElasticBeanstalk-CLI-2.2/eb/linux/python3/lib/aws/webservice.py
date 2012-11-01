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

from datetime import datetime
import random
import time
import urllib.request, urllib.parse, urllib.error
import urllib.request, urllib.error, urllib.parse
try:
    import simplejson as json
except ImportError:
    import json
import logging


from . import requests
from scli import prompt    
from scli.constants import ServiceDefault
from lib.aws.exception import AwsErrorCode
from lib.aws.exception import AwsServiceException
from lib.aws.http_client import CaValidationHttpsHandler
from lib.aws.signature import AWSSignature    
from lib.utility import misc


log = logging.getLogger('aws') 

HTTP_GET = 'GET'
HTTP_POST = 'POST'


#----------------------------------------------------
# Helper methods
def _exponential_backoff(max_tries):
    """
    Returns a series of floating point numbers between 0 and 2^i-1 for i in 0 to max_tries
    """
    return [random.random() * (2**i - 1) for i in range(0, max_tries)]


def _extend_backoff(durations):
    """
    Adds another exponential delay time to a list of delay times
    """
    durations.append(random.random() * (2**len(durations) - 1))

def _extractAwsErrorMessage(e):
    try :
        eDoc = json.loads(e.read().decode('utf-8'))['Error']
        return (misc.to_unicode(eDoc['Code']), misc.to_unicode(eDoc['Message']))
    except :
        return ('Error', '{0}:{1}'.format(e.code, e.msg))

    
    
class AWSQueryClient(object):
    '''
    Client implementing AWS/Query protocol
    '''
    
    _default_opener = urllib.request.build_opener(CaValidationHttpsHandler())
#    for handler in _default_opener.handlers:
#        if not isinstance(handler, urllib2.UnknownHandler):
#            handler._debuglevel = 1    

    def __init__(self, accessKey, secretKey, endpoint, result_format, signature_version, api_version):
        '''
        Constructor
        '''
        self._accessKey = accessKey
        self._secretKey = secretKey
        self._endpoint = endpoint
        self._result_format = result_format
        self._signature_version = signature_version
        self._api_version = api_version
        
        self._signer = AWSSignature(accessKey, secretKey, endpoint)

    def call(self, params, format_ = None,  method = HTTP_POST):
        
        if format_ is None: 
            format_ = self._result_format

        if method == HTTP_GET:        
            url = self._construct_get_url(params.get_dict())
            headers={'Accept' : 'application/' + format_,
                     'Accept-Charset' : ServiceDefault.CHAR_CODEC,
                     'User-Agent' : ServiceDefault.USER_AGENT}
                        
            result = self._request_with_retry(HTTP_GET, url, headers)
            
        elif method == HTTP_POST:
            url = self._endpoint if self._endpoint.endswith('/') else self._endpoint + '/'
            headers = {'Accept' : 'application/' + format_,
                       'Accept-Charset' : ServiceDefault.CHAR_CODEC,
                       'User-Agent' : ServiceDefault.USER_AGENT,
                       'Content-Type' : 'application/x-www-form-urlencoded',
                       'Expect' : '100-continue'}
            post_data = self._construct_post_data(params.get_dict())

            result = self._request_with_retry(HTTP_POST, url, headers, post_data)

        return result
            
    def _construct_get_url(self, inParams, verb=HTTP_GET):
        '''
        Construct AWS Query Get url 
        '''
        params = dict(inParams)

        params['SignatureVersion'] = self._signature_version
        params['Version'] = self._api_version
        params['AWSAccessKeyId'] = self._accessKey
        params['Timestamp'] = datetime.utcnow().isoformat()
        params['SignatureMethod'] = 'HmacSHA256'
        params['ContentType'] = 'JSON'
        params['Signature'] = self._signer.sign(verb, params)

        host = self._endpoint if self._endpoint.endswith('/') else self._endpoint + '/'
        return misc.to_bytes(host) + '?' + '&'.join\
            (urllib.parse.quote(misc.to_bytes(k)) + '=' + urllib.parse.quote(misc.to_bytes(v)) \
             for k, v in params.items())
    
    
    def _construct_post_data(self, inParams, verb=HTTP_POST):
        data = dict(inParams)

        data['SignatureVersion'] = self._signature_version
        data['Version'] = self._api_version
        data['AWSAccessKeyId'] = self._accessKey
        data['Timestamp'] = datetime.utcnow().isoformat()
        data['SignatureMethod'] = 'HmacSHA256'
        data['ContentType'] = 'JSON'
        data['Signature'] = self._signer.sign(verb, data)

        return misc.to_bytes('&'.join(urllib.parse.quote(misc.to_bytes(k)) + '=' \
                                      + urllib.parse.quote(misc.to_bytes(v)) \
                                      for k, v in data.items()))
    
    
    def _urlopen_withretry(self, request_or_url, max_tries = 5, 
                          http_error_extractor = _extractAwsErrorMessage, 
                          opener = _default_opener):
        """
        Exponentially retries up to max_tries to open request_or_url.
        Raises an IOError on failure
    
        http_error_extractor is a function that takes a urllib2.HTTPError and returns a tuple of
        (AWS error code, message)
        """
        durations = _exponential_backoff(max_tries)
        for index, length in enumerate(durations):
            if length > 0:
                log.debug('Sleeping for %f seconds before retrying', length)
                time.sleep(length)
    
            try:
                return opener.open(request_or_url)
            except urllib.error.HTTPError as ex:
                http_code = ex.code
                aws_code, message = http_error_extractor(ex)
                
                if http_code < 500 and aws_code != AwsErrorCode.Throttling:
                    raise AwsServiceException(message, aws_code, http_code)
                elif AwsErrorCode.Throttling == aws_code or http_code == 503:
                    _extend_backoff(durations)
                    
                if index + 1 < len(durations):
                    prompt.info('Error {0}:{1}. Wait {2} seconds before retry.'.\
                                 format(aws_code, message, durations[index + 1]))
                log.error(message + ' ' + aws_code)
                last_message = message
            except urllib.error.URLError as url_ex:
                log.error('URLError: %s', url_ex.reason)
                raise
        else:
            raise AwsServiceException(last_message, aws_code, http_code)


    def _request_with_retry(self, verb, url, headers, data, max_tries = 5):
    
        durations = _exponential_backoff(max_tries)
        
        for index, length in enumerate(durations):
            if length > 0:
                log.debug('Sleeping for %f seconds before retrying', length)
                time.sleep(length)
    
            try:
                if verb == HTTP_GET:
                    response = requests.get(url, headers = headers, verify=True)
                elif verb == HTTP_POST:
                    response = requests.post(url, data = data, headers = headers, verify=True)
                else:
                    raise AttributeError('Not supported HTTP action "{0}".'.format(verb))

                # check status code
                if response.status_code != 200:
                    http_code = response.status_code
                    try:
                        aws_code = response.json['Error']['Code']
                        message = response.json['Error']['Message']
                    except TypeError as ex:
                        raise AttributeError('HTTP {0}: {1}'.format(http_code, response.text))

                    if http_code < 500 and aws_code != AwsErrorCode.Throttling:
                        raise AwsServiceException(message, aws_code, http_code)
                    
                    elif AwsErrorCode.Throttling == aws_code or http_code == 503:
                        prompt.info('Request is throttled.')
                        _extend_backoff(durations)
                        
                    if index + 1 < len(durations):
                        prompt.info('Error {0}:{1}. Wait {2} seconds before retry.'.\
                                     format(aws_code, message, durations[index + 1]))
                    log.error(message + ' ' + aws_code)
                    last_message = message
                    
                else:
                    if response.json is None:
                        raise ValueError('Cannot parse response form {0}.'.format(response.url))
                    return response
            
            except requests.exceptions.SSLError as ex:
                log.error('SSL Error: %s', ex)
                raise
            
            except (requests.exceptions.HTTPError, 
                    requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout) as ex:
                log.error(ex)
                last_message = ex
                
        else:
            if aws_code is None:
                aws_code = ''
            if http_code is None:
                http_code = ''
            raise AwsServiceException(last_message, aws_code, http_code)


            
    
            
