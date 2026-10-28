"""Private object storage with a compatible local backend and verified file cache."""
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


class BlobStorage:
    def __init__(self, directory: Path):
        self.directory=directory.resolve();self.endpoint=os.getenv('MATHPDF_S3_ENDPOINT')
        self.remote=bool(self.endpoint);self.client=None
        if self.remote:
            credentials=json.loads(Path(os.environ['MATHPDF_S3_CREDENTIALS_FILE']).read_text())
            self.bucket=credentials.get('bucket','mathpdf');self.cache=self.directory/'object-cache'
            self.client=boto3.client('s3',endpoint_url=self.endpoint,region_name=credentials.get('region','garage'),
                aws_access_key_id=credentials['access_key_id'],aws_secret_access_key=credentials['secret_access_key'],
                config=Config(signature_version='s3v4',s3={'addressing_style':'path'},connect_timeout=5,read_timeout=45,
                    retries={'max_attempts':2},request_checksum_calculation='when_required',response_checksum_validation='when_required'))
        else:self.cache=self.directory
        self.cache.mkdir(parents=True,exist_ok=True)
    def _path(self,key):
        path=(self.cache/key).resolve()
        if not key or key.startswith('/') or '\\' in key or not path.is_relative_to(self.cache) or '..' in Path(key).parts:
            raise ValueError('Invalid private object key.')
        return path
    def put(self,key,data,content_type='application/octet-stream'):
        path=self._path(key)
        digest=hashlib.sha256(data).hexdigest()
        if self.remote:
            self.client.put_object(Bucket=self.bucket,Key=key,Body=data,ContentType=content_type,Metadata={'sha256':digest})
        path.parent.mkdir(parents=True,exist_ok=True);temporary=path.parent/(uuid4().hex+'.upload')
        try:temporary.write_bytes(data);temporary.replace(path)
        finally:temporary.unlink(missing_ok=True)
        return digest
    def path(self,key,expected_sha=None):
        path=self._path(key)
        if path.exists() and expected_sha and hashlib.sha256(path.read_bytes()).hexdigest()!=expected_sha:
            if not self.remote:raise ValueError('Stored object hash does not match its document.')
            path.unlink()
        if not path.is_file() and self.remote:
            response=self.client.get_object(Bucket=self.bucket,Key=key)
            try:data=response['Body'].read()
            finally:response['Body'].close()
            if expected_sha and hashlib.sha256(data).hexdigest()!=expected_sha:
                raise ValueError('Stored object hash does not match its document.')
            path.parent.mkdir(parents=True,exist_ok=True);temporary=path.parent/(uuid4().hex+'.download')
            try:temporary.write_bytes(data);temporary.replace(path)
            finally:temporary.unlink(missing_ok=True)
        if not path.is_file():raise ValueError('The stored file is missing.')
        return path
    def delete(self,key):
        path=self._path(key)
        if self.remote:self.client.delete_object(Bucket=self.bucket,Key=key)
        path.unlink(missing_ok=True)
    def copy(self,source,target,sha=None):
        self._path(source);self._path(target)
        if self.remote:
            self.client.copy_object(Bucket=self.bucket,Key=target,CopySource={'Bucket':self.bucket,'Key':source})
        else:self.put(target,self.path(source,sha).read_bytes())
    def verify(self,key,sha):
        # Verification reads the durable object, rather than accepting a warm cache.
        if self.remote:
            result=self.client.get_object(Bucket=self.bucket,Key=key)
            try:actual=hashlib.sha256(result['Body'].read()).hexdigest()
            finally:result['Body'].close()
        else:actual=hashlib.sha256(self.path(key).read_bytes()).hexdigest()
        if actual!=sha:raise ValueError('Durable object verification failed.')

    def retain(self,source,target,sha):
        """Keep a private diagnostic revision while removing its library key."""
        try:self.copy(source,target,sha)
        except ClientError as error:
            if str(error.response.get('Error',{}).get('Code')) not in {'404','NoSuchKey','NotFound'}:raise
            self.path(target,sha)
        except (FileNotFoundError,ValueError):self.path(target,sha)
        self.delete(source)
