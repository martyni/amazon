#!/bin/python
from pprint import pprint
import json
import re
import netaddr


class Environment(object):

    def exception(self, problem):
        raise BaseExeption(problem)

    def __init__(self, version="2010-09-09", description='A default environment', subnet_default=24):
        self.version = version
        self.outputs = {}
        self.id = "a"
        self.count = 0
        self.default_tags = [
            {"Key": "Application", "Value": self.ref("AWS::StackName")}
        ]
        self.description = description
        self.default_network = False
        self.subnet_default = subnet_default
        self.env = {
            "AWSTemplateFormatVersion": self.version,
            "Description": self.description,
            "Resources": {},
            "Outputs": {},
            "Metadata": {"AWS::CloudFormation::Designer": {}}
        }
        self.inventory_order = []
        self.inventory = {}

    def add_outputs(self, name, description='', target=None):
        self.env["Outputs"][name] = {
            "Value": self.ref(name),
            "Description": description
        }

    def counter(self):
        self.count += 1
        return self.count

    def get_first(self, _type):
        for resource in self.inventory_order:
            if _type == resource[0]:
                return resource[1]
        return False

    def cf_join(self, join_list, deliminator=""):
        return {"Fn::Join": [deliminator, join_list]}

    def cf_availability_zones(self, zone):
        return {"Fn::Select": [str(zone), {"Fn::GetAZs": {"Ref": "AWS::Region"}}]}

    def get_all(self, _type):
        return [resource[1] for resource in self.inventory_order if _type == resource[0]]

    def add_resource(self, name, _type, required, optional_keys, depends=None, **kwargs):
        name = name.title().replace(" ", "")
        self.add_outputs(name)
        if _type == "AWS::AutoScaling::AutoScalingGroup":
            temp_resource = Resource(_type,
                                     required,
                                     optional_keys,
                                     Tags=[{"Key": "Name", "Value": self.cf_join(
                                         [self.ref("AWS::StackName"), name]), "PropagateAtLaunch":True}],
                                     **kwargs)
        elif "Tags" in optional_keys and "Tags" not in kwargs:
            temp_resource = Resource(_type,
                                     required,
                                     optional_keys,
                                     Tags=self.default_tags +
                                     [{"Key": "Name", "Value": self.cf_join(
                                         [self.ref("AWS::StackName"), name])}],
                                     **kwargs)
        elif "Tags" in optional_keys:
            temp_resource = Resource(_type,
                                     required,
                                     optional_keys,
                                     Tags=self.default_tags +
                                     [{"Key": "Name", "Value": name}] +
                                     kwargs.pop("Tags"),
                                     **kwargs)
        else:
            temp_resource = Resource(_type,
                                     required,
                                     optional_keys,
                                     **kwargs)
        self.inventory_order.append((_type, name))
        self.inventory[name] = str(self.id)
        self.env["Resources"][name] = temp_resource.return_resource()
        if depends:
            self.env["Resources"][name]["DependsOn"] = depends
        self.env["Resources"][name]["Metadata"] = {
            "AWS::CloudFormation::Designer": {
                "id": str(self.id)
            }
        }
        self.id = chr(ord(self.id) + 1)

    def add_vpc(self, name, cidr_block="192.168.0.0/16", **kwargs):
        required_keys = {"CidrBlock": str}
        optional_keys = {
            "EnableDnsSupport": bool,
            "EnableDnsHostnames": bool,
            "InstanceTenancy": str,
            "Tags": list
        }
        self.add_resource(name,
                          "AWS::EC2::VPC",
                          required_keys,
                          optional_keys,
                          CidrBlock=cidr_block,
                          **kwargs)

        if not self.default_network:
            self.default_network = netaddr.IPNetwork(cidr_block)
            self.network_generator = self.default_network.subnet(
                self.subnet_default)

    def ref(self, key):
        return {"Ref": key}

    def cloudformation_designer(self, _id, source, target):
        self.env["Metadata"]["AWS::CloudFormation::Designer"][_id] = {
            "source": {
                "id": self.inventory[source]
            },
            "target": {
                "id": self.inventory[target]
            },
            "z": self.counter()
        }

    def add_subnet(self, name, vpc=None, cidr_block=None, **kwargs):
        vpc = self.get_first("AWS::EC2::VPC") if not vpc else vpc
        cidr_block = self.get_next_subnet() if not cidr_block else cidr_block
        required_keys = {
            "CidrBlock": str,
            "VpcId": dict
        }
        optional_keys = {
            "AvailabilityZone": dict,
            "MapPublicIpOnLaunch": bool,
            "Tags": list
        }
        self.add_resource(name,
                          "AWS::EC2::Subnet",
                          required_keys,
                          optional_keys,
                          VpcId=self.ref(vpc),
                          CidrBlock=cidr_block,
                          **kwargs
                          )

    def add_internet_gateway(self, name, subnets=None):
        self.add_resource(name,
                          "AWS::EC2::InternetGateway",
                          {},
                          {"Tags": list},
                          depends=subnets
                          )

    def attach_internet_gateway(self, name, vpc=None, subnets=None, gateway=None):
        gateway = self.get_first(
            "AWS::EC2::InternetGateway") if not gateway else gateway
        vpc = self.get_first("AWS::EC2::VPC") if not vpc else vpc
        required = {
            "VpcId": dict,
            "InternetGatewayId": dict
        }
        optional = {}
        self.cloudformation_designer(self.id, gateway, vpc)
        gateway_ref = self.ref(gateway)
        vpc_ref = self.ref(vpc)
        self.add_resource(name,
                          "AWS::EC2::VPCGatewayAttachment",
                          required,
                          optional,
                          depends=[vpc, gateway],
                          VpcId=vpc_ref,
                          InternetGatewayId=gateway_ref)

    def get_next_subnet(self):
        if self.default_network:
            return str(self.network_generator.next())

    def add_route_table(self, name, vpc=None, attached=None):
        vpc = self.ref(self.get_first("AWS::EC2::VPC")
                       ) if not vpc else self.ref(vpc)
        required = {"VpcId": dict}
        optional = {"Tags": list}
        attached = self.get_first(
            "AWS::EC2::VPCGatewayAttachment") if not attached else attached
        self.add_resource(name,
                          "AWS::EC2::RouteTable",
                          required,
                          optional,
                          depends=[attached],
                          VpcId=vpc)

    def add_route(self, name, cidr_block, route_table=None, depends=[],  **kwargs):
        route_table = self.get_first(
            "AWS::EC2::RouteTable") if not route_table else route_table
        route_table = self.ref(route_table)
        required = {
            "DestinationCidrBlock": str,
            "RouteTableId": dict
        }
        optional = {
            "GatewayId": dict,
            "InstanceId": dict,
            "NatGatewayId": dict,
            "NetworkInterfaceId": dict,
            "VpcPeeringConnectionId": dict
        }
        self.add_resource(name,
                          "AWS::EC2::Route",
                          required,
                          optional,
                          depends=depends,
                          RouteTableId=route_table,
                          DestinationCidrBlock=cidr_block,
                          **kwargs
                          )

    def add_default_internet_route(self, name):
        depends = [self.get_first("AWS::EC2::VPCGatewayAttachment")]
        gateway = self.ref(self.get_first("AWS::EC2::InternetGateway"))
        self.add_route(name, "0.0.0.0/0", depends=depends, GatewayId=gateway)

    def add_subnet_to_route_table(self, name, subnet=None, route_table=None):
        subnet = self.get_first("AWS::EC2::Subnet") if not subnet else subnet
        route_table = self.get_first(
            "AWS::EC2::RouteTable") if not route_table else route_table
        subnet_ref = self.ref(subnet)
        route_table_ref = self.ref(route_table)
        required = {
            "RouteTableId": dict,
            "SubnetId": dict
        }
        optional = {}
        depends = [subnet, route_table]
        self.add_resource(name,
                          "AWS::EC2::SubnetRouteTableAssociation",
                          required,
                          optional,
                          RouteTableId=route_table_ref,
                          SubnetId=subnet_ref
                          )

    def add_security_group(self, name, ingress, egress, vpc=None, **kwargs):
        vpc = self.get_first("AWS::EC2::VPC") if not vpc else vpc
        vpc_ref = self.ref(vpc)

        required = {
            "GroupDescription": str,
            "VpcId": dict
        }
        optional = {
            "Tags": list,
            "SecurityGroupEgress": list,
            "SecurityGroupIngress": list
        }
        self.add_resource(name,
                          "AWS::EC2::SecurityGroup",
                          required,
                          optional,
                          GroupDescription=self.describe(ingress, egress),
                          VpcId=vpc_ref,
                          SecurityGroupIngress=ingress,
                          SecurityGroupEgress=egress,
                          **kwargs)

    def add_launch_configuration(self, name, image, instance_type, vpc=None, security_groups=None, **kwargs):
        vpc = self.get_first("AWS::EC2::VPC") if not vpc else vpc
        security_groups = [self.ref(s) for s in self.get_all(
            "AWS::EC2::SecurityGroup")] if not security_groups else [self.ref(s) for s in security_groups]
        vpc_ref = self.ref(vpc)
        required = {
            "ImageId": str,
            "InstanceType": str
        }
        optional = {
            "AssociatePublicIpAddress": bool,
            "BlockDeviceMappings": list,
            "ClassicLinkVPCId": dict,
            "ClassicLinkVPCSecurityGroups": dict,
            "EbsOptimized": bool,
            "IamInstanceProfile": str,
            "InstanceId": dict,
            "InstanceMonitoring": bool,
            "KernelId": str,
            "KeyName": str,
            "PlacementTenancy": str,
            "RamDiskId": str,
            "SecurityGroups": list,
            "SpotPrice": str,
            "UserData": dict
        }
        self.add_resource(name,
                          "AWS::AutoScaling::LaunchConfiguration",
                          required,
                          optional,
                          depends=[vpc],
                          ImageId=image,
                          InstanceType=instance_type,
                          SecurityGroups=security_groups,
                          **kwargs)

    def add_autoscaling_group(self, name, max_size="1", min_size="0", subnets=None, instance=None, launch_config=None, **kwargs):
        subnets = [self.ref(s) for s in self.get_all(
            "AWS::EC2::Subnet")] if not subnets else [self.ref(s) for s in subnets]
        if not instance:
            launch_config = self.get_first(
                "AWS::AutoScaling::LaunchConfiguration") if not launch_config else launch_config
        required = {
            "MaxSize": str,
            "MinSize": str
        }
        optional = {
            "AvailabilityZones": list,
            "Cooldown": str,
            "DesiredCapacity": str,
            "HealthCheckGracePeriod": int,
            "HealthCheckType": str,
            "InstanceId": dict,
            "LaunchConfigurationName": dict,
            "LoadBalancerNames": dict,
            "MetricsCollection": list,
            "NotificationConfigurations": list,
            "PlacementGroup": str,
            "Tags": list,
            "TargetGroupARNs": list,
            "TerminationPolicies": list,
            "VPCZoneIdentifier": list
        }
        if launch_config:
            self.add_resource(name,
                              "AWS::AutoScaling::AutoScalingGroup",
                              required,
                              optional,
                              MaxSize=max_size,
                              MinSize=min_size,
                              VPCZoneIdentifier=subnets,
                              LaunchConfigurationName=self.ref(launch_config),
                              **kwargs
                              )
        elif instances:
            self.add_resource(name,
                              "AWS::AutoScaling::AutoScalingGroup",
                              required,
                              optional,
                              MaxSize=max_size,
                              MinSize=min_size,
                              VPCZoneIdentifier=subnets,
                              InstanceId=self.ref(instance),
                              **kwargs
                              )

    def describe(self, *args):
        description = '_'.join([str(arg) for arg in args])
        return re.sub(r'\W+', ' ', description)[:255:]

    def show_resources(self):
        return self.env
    
    def write_resources(self, filename):
       with open(filename, 'w') as cf:
          cf.write(json.dumps(self.show_resources))


class SecurityGroupRules(object):

    def exception(self, problem):
        raise BaseException(problem)

    def __init__(self, _type):
        self.type = _type
        self.rules = []
        self.options = "SecurityGroupIngress", "SecurityGroupEgress"
        if self.type not in self.options:
            self.exception(
                "Type set incorecctly must be in {}".format(self.options))

    def add_rule(self, ip_protocol, cidr_ip=None, from_port=None, to_port=None, source_security_group_id=None, source_security_group_name=None, destination_security_group_id=None):
        raw_rule = {
            "IpProtocol": ip_protocol,
            "CidrIp": cidr_ip,
            "FromPort": from_port,
            "ToPort": to_port,
            "SourceSecurityGroupId": source_security_group_id,
            "SourceSecurityGroupName": source_security_group_name,
            "DestinationSecurityGroupId": destination_security_group_id
        }

        if self.type == "SecurityGroupIngress" and destination_security_group_id:
            self.exception(
                "Ingress and destiniation_security_group_id incompatible")
        elif self.type == "SecurityGroupEgress" and source_security_group_name or source_security_group_id:
            self.exception(
                "Engress and source_security_group_id/name incompatible")
        for key in raw_rule:
            if raw_rule[key] and key in ("FromPort", "ToPort"):
                if type(raw_rule[key]) != int:
                    self.exception("{} should be int, got {}".format(
                        key, type(raw_rule[key])))
            elif raw_rule[key]:
                if type(raw_rule[key]) != str:
                    self.exception("{} should be str, got {}".format(
                        key, type(raw_rule[key])))
        self.rules.append({key: raw_rule[key]
                           for key in raw_rule if raw_rule[key]})


class Resource(object):

    def exception(self, problem):
        raise BaseException(problem)

    def __init__(self, _type, required_keys, optional_keys,  **kwargs):
        self.type = _type
        self.keys = {
            "Required": {key: required_keys[key] for key in required_keys},
            "All": {key: optional_keys[key] for key in optional_keys}
        }
        for key in self.keys["Required"]:
            self.keys["All"][key] = self.keys["Required"][key]
        self.object = {}
        if kwargs:
            for key in self.keys["Required"]:
                if key not in kwargs:
                    self.exception('{} required'.format(key))

            for key in kwargs:
                self.object[key] = kwargs[key] if type(kwargs[key]) == self.keys["All"][key] else self.exception(
                    '''{} is wrong format {} {}'''.format(key, type(kwargs[key]), self.keys["All"][key]))

    def return_resource(self):
        return {"Type": self.type, "Properties": self.object}

class Cloud_formation_client(object):
   def __init__(self, name, bucket_name='cloudformation', file_name, on_failure='DELETE'):
      self.cf = boto3.client('cloudformation')
      self.s3 = boto3.resource('s3')
      self.name = name
      self.bucket_name = bucket_name
      self.file_name = file_name
      self.on_failure = on_failure

   def create_bucket(self, **kwargs):
      self.s3.create_bucket(
         Bucket = self.bucket_name,
         **kwargs
      )

   def upload_to_s3(self, **kwargs):
      try:
         with open(self.filename, 'r') as cf: 
            self.s3.Bucket(self.bucket_name).put_object(
               Key=self.filename, 
               Body=cf,
               **kwargs
            )
      except:
         self.create_bucket()
         self.upload_to_s3()   

   def create_stack(self ):
      self.cf.create_stack(
         StackName = self.name,
         TemplateURL = self.url,
         Capabilities = ['CAPABILITY_IAM'],
         OnFailure = self.on_failure
      )

if __name__ == "__main__":
    my_env = Environment()
    my_env.add_vpc("VPC")
    my_env.add_subnet("My first subnet", AvailabilityZone={
                      "Fn::Select": ["1", {"Fn::GetAZs": {"Ref": "AWS::Region"}}]})
    my_env.add_subnet("My second subnet", AvailabilityZone={
                      "Fn::Select": ["2", {"Fn::GetAZs": {"Ref": "AWS::Region"}}]})
    my_env.add_internet_gateway("internet gateway")
    my_env.attach_internet_gateway("Attach gateway")
    my_env.add_route_table("My default route table")
    my_env.add_default_internet_route("To the internet")
    my_env.add_subnet_to_route_table("add first subnet")
    my_env.add_subnet_to_route_table(
        "add second subnet", subnet="MySecondSubnet")
    in_rules = SecurityGroupRules("SecurityGroupIngress")
    in_rules.add_rule("tcp", from_port=22, to_port=22, cidr_ip="0.0.0.0/0")
    out_rules = SecurityGroupRules("SecurityGroupEgress")
    out_rules.add_rule("-1", cidr_ip="0.0.0.0/0")
    my_env.add_security_group(
        "My security group", in_rules.rules, out_rules.rules)
    my_env.add_launch_configuration(
        "my launch configuration", "ami-64385917", "t2.micro")
    my_env.add_autoscaling_group("my autoscaling group")
    print json.dumps(my_env.show_resources())
    my_env.write_resources('file.json')
