import os
import boto3
import string
import random
from pprint import pprint
from fabric.api import local

if 'martyn' in os.environ.get('VIRTUAL_ENV', ''):
   boto3 = boto3.Session(profile_name='martyn')

def random_str(size=6, chars=string.ascii_lowercase):
   return ''.join(random.choice(chars) for _ in range(size))

class Cloudformation(object):
   def __init__(self, name, filename, region='eu-west-1', bucket_name='cloudformation', on_failure='DELETE', randomize_bucket=True):
      self.cf = boto3.client('cloudformation')
      self.s3 = boto3.client('s3')
      self.name = name 
      self.region = region
      if randomize_bucket:
         self.bucket_name = bucket_name + random_str()
      else:
         self.bucket_name = bucket_name
      self.filename = filename
      self.on_failure = on_failure
      self.upload_to_s3()

   def create_bucket(self, **kwargs):
      print 'Creating : {}'.format(self.bucket_name)
      self.s3.create_bucket(Bucket=self.bucket_name)

   def upload_to_s3(self, **kwargs):
      self.create_bucket()
      obj = {
         'Body': open(self.filename, 'r'),
         'Key': self.filename,
         'Bucket': self.bucket_name
      }
      print 'Uploading {} to {}'.format(
         self.filename,
         self.bucket_name
      )
      self.s3.put_object( **obj )

      
   def create_stack(self ):
      self.url = "https://s3.amazonaws.com/{}/{}".format(
         self.bucket_name,
         self.filename
      )
      obj = {
         'StackName' : self.name,
         'TemplateURL' : self.url,
         'Capabilities' : ['CAPABILITY_IAM'],
          'OnFailure' : self.on_failure
      }
      print 'Creating stack', 
      pprint(obj)
      self.cf.create_stack( **obj )

if __name__ == "__main__":
   c = Cloudformation('test', 'file.json')
   c.create_stack()
