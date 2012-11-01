#!/bin/sh

# Copyright 2012 Amazon.com, Inc. or its affiliates. All Rights
# Reserved.
# 
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy
# of the License is located at
#
#   http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the
# specific language governing permissions and limitations under the
# License.

git config alias.aws.elasticbeanstalk.remote "!ruby -ropenssl -e 'def gv(n); IO.popen(%Q(git config --get #{n})) { |f| f.read.strip }; end; def gi(); IO.popen(%Q(git rev-parse HEAD)) { |f| f.read.strip }; end; def gvbs(v); gv(%Q(aws.elasticbeanstalk.#{v})); end; D=OpenSSL::Digest::Digest; def hmac(d,s); OpenSSL::HMAC.digest(D.new(%q(sha256)), s, d); end; def ch(d) [d,gv(%q(aws.region)),%q(devtools),%q(aws4_request)]; end; def hex(d); d.to_s.unpack(%q(H*)).first; end; t = Time.now.utc.strftime(%q(%Y%m%dT%H%M%S)); d = t[0..7]; h = gvbs(%q(host)); path = %Q(/v1/repos/#{hex(gvbs(%q(application)))}/commitid/#{hex(gi)}); env = gvbs(%q(environment)); path += %Q(/environment/#{hex(env)}) unless env.empty?; ms = %q(AWS4)+gv(%q(aws.secretkey)); rs = D.hexdigest(%q(sha256),%Q(GIT\n#{path}\n\nhost:#{h}\n\nhost\n)); sts = %Q(AWS4-HMAC-SHA256\n#{t}\n#{ch(d).join(%q(/))}\n#{rs}); pass = hex(hmac(sts,ch(d).inject(ms) { |s,i| hmac(i,s) })); STDOUT.write(%Q(https://#{gv(%q(aws.accesskey))}:#{t}Z#{pass}@#{h}#{path}))'"
git config aws.endpoint.us-east-1 git.elasticbeanstalk.us-east-1.amazonaws.com
git config aws.endpoint.ap-northeast-1 git.elasticbeanstalk.ap-northeast-1.amazonaws.com
git config aws.endpoint.eu-west-1 git.elasticbeanstalk.eu-west-1.amazonaws.com
git config aws.endpoint.us-west-1 git.elasticbeanstalk.us-west-1.amazonaws.com
git config aws.endpoint.us-west-2 git.elasticbeanstalk.us-west-2.amazonaws.com
git config aws.endpoint.ap-southeast-1 git.elasticbeanstalk.ap-southeast-1.amazonaws.com
git config alias.aws.elasticbeanstalk.push '!git push -f `git aws.elasticbeanstalk.remote` HEAD:refs/heads/master'
git config alias.aws.push '!git aws.elasticbeanstalk.push $@'
git config alias.aws.elasticbeanstalk.config "!ruby -e 'def set(n,v); system(%Q(git),%Q(config),%Q(aws.#{n}),%Q(#{v})); end; def get(n); v = IO.popen(%Q(git config --get aws.#{n})) { |f| f.read.strip }; v unless v.to_s.strip.empty?; end; def prompt(m,n,d=nil); d = get(n) || d; m << %Q( [default to #{d}]) unless d.nil?; STDOUT.write(%Q(#{m}: )); STDOUT.flush; v = STDIN.gets.to_s.strip; if v.empty?; set(n, d) unless d.nil?; else; set(n, v); end; end; def ep(r); get(%Q(endpoint.#{r})); end; d = ep(%q(us-east-1)); prompt(%q(AWS Access Key), :accesskey); prompt(%q(AWS Secret Key), :secretkey); prompt(%q(AWS Region), :region, %q(us-east-1)); h = ep(get(:region)); if (h.nil?); prompt(%q(AWS Host), %q(elasticbeanstalk.host), d); else; set(%q(elasticbeanstalk.host), h); end; prompt(%q(AWS Elastic Beanstalk Application), %q(elasticbeanstalk.application)); prompt(%q(AWS Elastic Beanstalk Environment), %q(elasticbeanstalk.environment))'"
git config alias.aws.config '!git aws.elasticbeanstalk.config $@'
