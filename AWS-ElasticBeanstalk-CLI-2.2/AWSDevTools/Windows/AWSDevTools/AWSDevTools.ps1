$awsSource = @"
using System;
using System.Globalization;
using System.Text;
using System.Security.Cryptography;

namespace Amazon.DevTools
{
    public class AWSUser
    {
        public string AccessKey
        {
            get;
            set;
        }

        public string SecretKey
        {
            get;
            set;
        }

        protected internal void Validate()
        {
            if (string.IsNullOrEmpty(this.AccessKey))
            {
                throw new InvalidOperationException("[AccessKey]");
            }
            if (string.IsNullOrEmpty(this.SecretKey))
            {
                throw new InvalidOperationException("[SecretKey]");
            }
        }
    }
}

namespace Amazon.DevTools
{
    public abstract class AWSDevToolsRequest
    {
        protected const string METHOD = "GIT";
        protected const string SERVICE = "devtools";

        DateTime dateTime;

        public AWSDevToolsRequest()
            : this(DateTime.UtcNow)
        {
        }

        public AWSDevToolsRequest(DateTime dateTime)
        {
            if (dateTime == null)
            {
                throw new ArgumentNullException("dateTime");
            }
            this.dateTime = dateTime.ToUniversalTime();
        }

        public string DateStamp
        {
            get
            {
                return this.dateTime.ToString("yyyyMMdd", CultureInfo.InvariantCulture);
            }
        }

        public string DateTimeStamp
        {
            get
            {
                return this.dateTime.ToString("yyyyMMddTHHmmss", CultureInfo.InvariantCulture);
            }
        }

        public abstract string DerivePath();

        protected internal abstract string DeriveRequest();

        public string Host
        {
            get;
            set;
        }

        public string Region
        {
            get;
            set;
        }

        public string Service
        {
            get
            {
                return AWSDevToolsRequest.SERVICE;
            }
        }

        protected internal virtual void Validate()
        {
            if (string.IsNullOrEmpty(this.Host))
            {
                throw new InvalidOperationException("[Host]");
            }
            if (string.IsNullOrEmpty(this.Region))
            {
                throw new InvalidOperationException("[Region]");
            }
        }
    }
}

namespace Amazon.DevTools
{
    public class AWSElasticBeanstalkRequest : AWSDevToolsRequest
    {
        public AWSElasticBeanstalkRequest()
            : base()
        {
        }

        public AWSElasticBeanstalkRequest(DateTime dateTime)
            : base(dateTime)
        {
        }

        public string Application
        {
            get;
            set;
        }

        public override string DerivePath()
        {
            this.Validate();

            string path = null;
         
            if (string.IsNullOrEmpty(this.Environment))
            {
                path = string.Format("/v1/repos/{0}/commitid/{1}"
		, this.Encode(this.Application)
		, this.Encode(this.CommitId));
            }
            else
            {
                path = string.Format("/v1/repos/{0}/commitid/{1}/environment/{2}"
		, this.Encode(this.Application)
		, this.Encode(this.CommitId)
		, this.Encode(this.Environment));
            }
            return path;
        }

        protected internal override string DeriveRequest()
        {
            this.Validate();

            string path = this.DerivePath();
            string request = string.Format("{0}\n{1}\n\nhost:{2}\n\nhost\n", AWSDevToolsRequest.METHOD, path, this.Host);
            return request;
        }

        public string Environment
        {
            get;
            set;
        }

	public string CommitId
	{
	   get;
	   set;
	}

        protected internal override void Validate()
        {
            base.Validate();
            if (string.IsNullOrEmpty(this.Application))
            {
                throw new InvalidOperationException("[Application]");
            }
            if (string.IsNullOrEmpty(this.Host))
            {
                throw new InvalidOperationException("[Host]");
            }
        }

	protected internal string Encode(string plaintext)
	{
	    StringBuilder sb = new StringBuilder();
	    foreach (byte b in new UTF8Encoding().GetBytes(plaintext))
	    {
		sb.Append(b.ToString("x2", CultureInfo.InvariantCulture));
	    }
	    return sb.ToString();
	}

    }
}

namespace Amazon.DevTools
{
    public class AWSDevToolsAuth
    {
        const string AWS_ALGORITHM = "HMAC-SHA256";
        const string HASH_ALGORITHM = "SHA-256";
        const string HMAC_ALGORITHM = "HMACSHA256";
        const string SCHEME = "AWS4";
        const string TERMINATOR = "aws4_request";

        AWSUser user;
        AWSDevToolsRequest request;

        public AWSDevToolsAuth(AWSUser user, AWSDevToolsRequest request)
        {
            this.user = user;
            this.request = request;
        }

        static byte[] DeriveKey(AWSUser user, AWSDevToolsRequest request)
        {
            string secret = string.Format("{0}{1}", AWSDevToolsAuth.SCHEME, user.SecretKey);
            byte[] kSecret = Encoding.UTF8.GetBytes(secret);
            byte[] kDate = AWSDevToolsAuth.Hash(AWSDevToolsAuth.HMAC_ALGORITHM, kSecret, Encoding.UTF8.GetBytes(request.DateStamp));
            byte[] kRegion = AWSDevToolsAuth.Hash(AWSDevToolsAuth.HMAC_ALGORITHM, kDate, Encoding.UTF8.GetBytes(request.Region));
            byte[] kService = AWSDevToolsAuth.Hash(AWSDevToolsAuth.HMAC_ALGORITHM, kRegion, Encoding.UTF8.GetBytes(request.Service));
            byte[] key = AWSDevToolsAuth.Hash(AWSDevToolsAuth.HMAC_ALGORITHM, kService, Encoding.UTF8.GetBytes(AWSDevToolsAuth.TERMINATOR));
            return key;
        }

        public string DerivePassword()
        {
            this.user.Validate();
            this.request.Validate();

            string signature = AWSDevToolsAuth.SignRequest(this.user, this.request);
            string password = string.Format("{0}Z{1}", this.request.DateTimeStamp, signature);
            return password;
        }

        public Uri DeriveRemote()
        {
            this.request.Validate();

            string path = this.request.DerivePath();
            string password = this.DerivePassword();
            string username = this.DeriveUserName();
            UriBuilder remote = new UriBuilder()
            {
                Host = this.request.Host,
                Path = path,
                Password = password,
                Scheme = "https",
                UserName = username,
            };
            return remote.Uri;
        }

        public string DeriveUserName()
        {
            this.user.Validate();

            return this.user.AccessKey;
        }

        static byte[] Hash(string algorithm, byte[] message)
        {
            HashAlgorithm hash = HashAlgorithm.Create(algorithm);
            byte[] digest = hash.ComputeHash(message);
            return digest;
        }

        static byte[] Hash(string algorithm, byte[] key, byte[] message)
        {
            KeyedHashAlgorithm hash = KeyedHashAlgorithm.Create(algorithm);
            hash.Key = key;
            byte[] digest = hash.ComputeHash(message);
            return digest;
        }

        static string SignRequest(AWSUser user, AWSDevToolsRequest request)
        {
            string scope = string.Format("{0}/{1}/{2}/{3}", request.DateStamp, request.Region, request.Service, AWSDevToolsAuth.TERMINATOR);
            StringBuilder stringToSign = new StringBuilder();
            stringToSign.AppendFormat("{0}-{1}\n{2}\n{3}\n", AWSDevToolsAuth.SCHEME, AWSDevToolsAuth.AWS_ALGORITHM, request.DateTimeStamp, scope);
            byte[] requestBytes = Encoding.UTF8.GetBytes(request.DeriveRequest());
            byte[] requestDigest = AWSDevToolsAuth.Hash(AWSDevToolsAuth.HASH_ALGORITHM, requestBytes);
            stringToSign.Append(AWSDevToolsAuth.ToHex(requestDigest));
            byte[] key = AWSDevToolsAuth.DeriveKey(user, request);
            byte[] digest = AWSDevToolsAuth.Hash(AWSDevToolsAuth.HMAC_ALGORITHM, key, Encoding.UTF8.GetBytes(stringToSign.ToString()));
            string signature = AWSDevToolsAuth.ToHex(digest);
            return signature;
        }

        static string ToHex(byte[] data)
        {
            StringBuilder hex = new StringBuilder();
            foreach (byte b in data)
            {
                hex.Append(b.ToString("x2", CultureInfo.InvariantCulture));
            }
            return hex.ToString();
        }
    }
}
"@

Add-Type -Language CSharpVersion3 -TypeDefinition $awsSource

function Edit-AWSElasticBeanstalkRemote
{
    $awsAccessKey = &git config --get aws.accesskey
    if ($awsAccessKey)
    {
        $awsAccessKeyInput = Read-Host "AWS Access Key [default to $($awsAccessKey)]"
    }
    else
    {
        $awsAccessKeyInput = Read-Host "AWS Access Key"
    }
    if ($awsAccessKeyInput)
    {
        $awsAccessKey = $awsAccessKeyInput
        &git config aws.accesskey $awsAccessKey
    }

    $awsSecretKey = &git config --get aws.secretkey
    if ($awsSecretKey)
    {
        $awsSecretKeyInput = Read-Host "AWS Secret Key [default to $($awsSecretKey)]"
    }
    else
    {
        $awsSecretKeyInput = Read-Host "AWS Secret Key"
    }
    if ($awsSecretKeyInput)
    {
        $awsSecretKey = $awsSecretKeyInput
        &git config aws.secretkey $awsSecretKey
    }

    $awsRegion = &git config --get aws.region
    if (-not $awsRegion)
    {
        $awsRegion = "us-east-1"
        &git config aws.region $awsRegion
    }
    $awsRegionInput = Read-Host "AWS Region [default to $($awsRegion)]"
    if ($awsRegionInput)
    {
        $awsRegion = $awsRegionInput
        &git config aws.region $awsRegion
    }

    switch ($awsRegion)
    {
        "us-east-1" { $awsHost = "git.elasticbeanstalk.us-east-1.amazonaws.com" }
        "ap-northeast-1" { $awsHost = "git.elasticbeanstalk.ap-northeast-1.amazonaws.com" }
        "ap-southeast-1" { $awsHost = "git.elasticbeanstalk.ap-southeast-1.amazonaws.com" }
        "eu-west-1" { $awsHost = "git.elasticbeanstalk.eu-west-1.amazonaws.com" } 
        "us-west-1" { $awsHost = "git.elasticbeanstalk.us-west-1.amazonaws.com" }
        "us-west-2" { $awsHost = "git.elasticbeanstalk.us-west-2.amazonaws.com" } 
    }
    if ($awsHost)
    {
        &git config aws.elasticbeanstalk.host $awsHost
    }
    else
    {
        $awsHostInput = Read-Host "AWS Host [default to git.elasticbeanstalk.us-east-1.amazonaws.com]"
    
        if ($awsHostInput)
        {
            $awsHost = $awsHostInput
            &git config aws.elasticbeanstalk.host $awsHost
        }
        else
        {
            &git config aws.elasticbeanstalk.host "git.elasticbeanstalk.us-east-1.amazonaws.com"
        }
    }

    $awsApplication = &git config --get aws.elasticbeanstalk.application
    if ($awsApplication)
    {
        $awsApplicationInput = Read-Host "AWS Elastic Beanstalk Application [default to $($awsApplication)]"
    }
    else
    {
        $awsApplicationInput = Read-Host "AWS Elastic Beanstalk Application"
    }
    if ($awsApplicationInput)
    {
        $awsApplication = $awsApplicationInput
        &git config aws.elasticbeanstalk.application $awsApplication
    }

    $awsEnvironment = &git config --get aws.elasticbeanstalk.environment
    if ($awsEnvironment)
    {
        $awsEnvironmentInput = Read-Host "AWS Elastic Beanstalk Environment [default to $($awsEnvironment)]"
    }
    else
    {
        $awsEnvironmentInput = Read-Host "AWS Elastic Beanstalk Environment"
    }
    if ($awsEnvironmentInput)
    {
        $awsEnvironment = $awsEnvironmentInput
        &git config aws.elasticbeanstalk.environment $awsEnvironment
    }
}

function Get-AWSElasticBeanstalkRemote
{
    trap [System.Management.Automation.MethodInvocationException]
    {
        if ($_.Exception -and $_.Exception.InnerException)
        {
            $awsOption = $_.Exception.InnerException.Message
            switch ($awsOption)
            {
                "[AccessKey]" { $awsOption = "aws.accesskey" }
                "[Application]" { $awsOption = "aws.elasticbeanstalk.application" }
                "[Host]" { $awsOption = "aws.elasticbeanstalk.host" }
                "[Region]" { $awsOption = "aws.region" }
                "[SecretKey]" { $awsOption = "aws.secretkey" }
            }
            Write-Host "Missing configuration setting for: $($awsOption)"
        }
        else
        {
            Write-Host "An unknown error occurred while computing your temporary password."
        }
        Write-Host "`nTry running 'git aws.config' to update your repository configuration.  You can also use 'git config --list' to check your configuration for a setting missing or misspelled."
        Exit
    }

    $awsAccessKey = &git config --get aws.accesskey
    $awsSecretKey = &git config --get aws.secretkey
    $awsRegion = &git config --get aws.region
    $awsHost = &git config --get aws.elasticbeanstalk.host
    $awsApplication = &git config --get aws.elasticbeanstalk.application
    $awsEnvironment = &git config --get aws.elasticbeanstalk.environment

    $gitCommitId = &git rev-parse HEAD

    $awsUser = New-Object -TypeName Amazon.DevTools.AWSUser
    $awsUser.AccessKey = $awsAccessKey
    $awsUser.SecretKey = $awsSecretKey

    $awsRequest = New-Object -TypeName Amazon.DevTools.AWSElasticBeanstalkRequest
    $awsRequest.Region = $awsRegion
    $awsRequest.Host = $awsHost
    $awsRequest.Application = $awsApplication
    $awsRequest.Environment = $awsEnvironment
    $awsRequest.CommitId = $gitCommitId

    $awsAuth = New-Object -TypeName Amazon.DevTools.AWSDevToolsAuth $awsUser,$awsRequest
    $awsRemote = $awsAuth.DeriveRemote()
    return $awsRemote.ToString()
}

function Invoke-AWSElasticBeanstalkPush
{
    $remote = Get-AWSElasticBeanstalkRemote
    &git push -f $remote HEAD:refs/heads/master
}

function Initialize-AWSElasticBeanstalkRepository
{
    &git config alias.aws.elasticbeanstalk.remote "!powershell -noprofile -executionpolicy bypass -command '& { Import-Module AWSDevTools; Get-AWSElasticBeanstalkRemote }'"
    &git config alias.aws.push "!powershell -noprofile -executionpolicy bypass -command '& { Import-Module AWSDevTools; Invoke-AWSElasticBeanstalkPush }'"
    &git config alias.aws.config "!powershell -noprofile -executionpolicy bypass -command '& { Import-Module AWSDevTools; Edit-AWSElasticBeanstalkRemote }'"
}

function Install-AWSDevToolsModule
{
    $userPath = $env:PSModulePath.split(";")[0]
    $modulePath = Join-Path $userPath -ChildPath AWSDevTools
    if (-not (Test-Path $modulePath))
    {
        New-Item -Path $modulePath -ItemType directory | Out-Null
    }
    Get-ChildItem AWSDevTools -Recurse | ForEach-Object { Copy-Item $_.fullName -Destination $modulePath -Force }
}

