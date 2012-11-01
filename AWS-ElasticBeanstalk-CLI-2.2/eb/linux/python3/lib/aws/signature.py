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

import urllib.parse
import urllib.request, urllib.parse, urllib.error
import base64
import hashlib
import hmac

from lib.utility import misc

class AWSSignature:
    
    def __init__(self, accesskey, secretkey, endpoint, signature_version = 2):
        '''
        Constructor
        '''
        self._accesskey = accesskey
        self._secretkey = secretkey
        self._endpoint = endpoint        
        self._signature_version = signature_version

        

    def v2_sign(self, verb, params):
        #TODO: Now this assumes path is always '/'.
        stringToSign = verb + '\n' + urllib.parse.urlsplit(self._endpoint)[1] + '\n/\n'
    
        stringToSign += '&'.join(urllib.parse.quote(misc.to_bytes(k), safe='~') \
                                 + '=' + urllib.parse.quote(misc.to_bytes(v), safe='~') \
                            for k, v in sorted(params.items()))
    
        return base64.b64encode(hmac.new(misc.to_bytes(self._secretkey), 
                                         misc.to_bytes(stringToSign), 
                                         hashlib.sha256).digest())
        
        
    def sign(self, verb, params):
        if self._signature_version == 2:
            return self.v2_sign(verb, params)
        raise AttributeError('Not supported signature version: "{0}"'.\
                             format(self._signature_version))
