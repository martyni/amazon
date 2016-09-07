#!/bin/python
from pprint import pprint
import json
import re
import netaddr
import os
from amazon_client import Cloudformation
from helper import (
    Listener,
    SecurityGroupRules,
    Resource
)


class Environment(object):

    def exception(self, problem):
        '''base exception method'''
        raise BaseExeption(problem)

    def __init__(self, name, version="2010-09-09", description='A default environment', subnet_default=24):
        '''Class for creating Amazon Cloudformation templates with minimal overhead'''
        self.version = version
        self.outputs = {}
        self.id = "a"
        self.count = 0
        self.name = name
        self.dir = os.path.dirname(os.path.realpath(
            __file__)) + '/{}'.format(self.name)
        try:
            os.stat(self.dir)
        except OSError:
            os.mkdir(self.dir)

        self.default_tags = [
            {"Key": "Application", "Value": self.cf_ref("AWS::StackName")}
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


    def counter(self):
        '''Keeps track of the number of resources'''
        self.count += 1
        return self.count

    def get_first(self, _type):
        '''Gets first resources of type _type. Environment knows what order resources are added within the script so this will be the first resource created in the script'''
        for resource in self.inventory_order:
            if _type == resource[0]:
                return resource[1]
        return False

    def get_all(self, _type):
        '''Gets a list of all the resources of type _type.'''
        return [resource[1] for resource in self.inventory_order if _type == resource[0]]

    def describe(self, *args):
        '''Returns a formatted string given arbitrary args'''
        description = '_'.join([str(arg) for arg in args])
        return re.sub(r'\W+', ' ', description)[:255:]

    def show_resources(self):
        '''Shows all the resources'''
        return self.env

    def write_resources(self, filename):
        '''Writes cloudformation object to file'''
        with open(filename, 'w+') as cf:
            cf.write(json.dumps(self.show_resources()))

    def cf_ref(self, key)e
        '''Cloudformation referential function'''
        return {"Ref": key}

    def cf_designer(self, _id, source, target):
        '''Implements the Cloudformation Designer. This was used for debugging and hasn't been fully implemented'''
        self.env["Metadata"]["AWS::CloudFormation::Designer"][_id] = {
            "source": {
                "id": self.inventory[source]
            },
            "target": {
                "id": self.inventory[target]
            },
            "z": self.counter()
        }

    def cf_join(self, join_list, deliminator=""):
        '''Join function'''
        return {"Fn::Join": [deliminator, join_list]}

    def cf_availability_zones(self, zone):
        '''Availability zone function'''
        return {"Fn::Select": [str(zone), {"Fn::GetAZs": {"Ref": "AWS::Region"}}]}

    def add_outputs(self, name, description='', target=None):
        '''Method to add output for resource'''
        self.env["Outputs"][name] = {
            "Value": self.cf_ref(name),
            "Description": description
        }

    def add_resource(self, name, _type, required, optional_keys, depends=None, **kwargs):
        '''Generic method for adding a resource to the Cloud formation template. Makes use of the Resource helper object'''
        name = name.title().replace(" ", "")
        self.add_outputs(name)
        if _type == "AWS::AutoScaling::AutoScalingGroup":
            temp_resource = Resource(_type,
                                     required,
                                     optional_keys,
                                     Tags=[{"Key": "Name", "Value": self.cf_join(
                                         [self.cf_ref("AWS::StackName"), name]), "PropagateAtLaunch":True}],
                                     **kwargs)
        elif "Tags" in optional_keys and "Tags" not in kwargs:
            temp_resource = Resource(_type,
                                     required,
                                     optional_keys,
                                     Tags=self.default_tags +
                                     [{"Key": "Name", "Value": self.cf_join(
                                         [self.cf_ref("AWS::StackName"), name])}],
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
        with open('{}/{}.json'.format(self.name, name), "w") as template:
            template.write(json.dumps(temp_resource.return_resource()))
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
                          VpcId=self.cf_ref(vpc),
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
        self.cf_designer(self.id, gateway, vpc)
        gateway_ref = self.cf_ref(gateway)
        vpc_ref = self.cf_ref(vpc)
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
        vpc = self.cf_ref(self.get_first("AWS::EC2::VPC")
                       ) if not vpc else self.cf_ref(vpc)
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
        route_table = self.cf_ref(route_table)
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
        gateway = self.cf_ref(self.get_first("AWS::EC2::InternetGateway"))
        self.add_route(name, "0.0.0.0/0", depends=depends, GatewayId=gateway)

    def add_subnet_to_route_table(self, name, subnet=None, route_table=None):
        subnet = self.get_first("AWS::EC2::Subnet") if not subnet else subnet
        route_table = self.get_first(
            "AWS::EC2::RouteTable") if not route_table else route_table
        subnet_ref = self.cf_ref(subnet)
        route_table_ref = self.cf_ref(route_table)
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
        vpc_ref = self.cf_ref(vpc)

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
        security_groups = [self.cf_ref(s) for s in self.get_all(
            "AWS::EC2::SecurityGroup")] if not security_groups else [self.cf_ref(s) for s in security_groups]
        vpc_ref = self.cf_ref(vpc)
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
        depends = [vpc]
        if "depends" in kwargs:
            depends += kwargs.pop("depends")
        self.add_resource(name,
                          "AWS::AutoScaling::LaunchConfiguration",
                          required,
                          optional,
                          depends=depends,
                          ImageId=image,
                          InstanceType=instance_type,
                          SecurityGroups=security_groups,
                          **kwargs)

    def add_loadbalancer(self, name, listeners, cross_zone=True, subnets=None, security_groups=None,  **kwargs):
        subnets = [self.cf_ref(s) for s in self.get_all(
            "AWS::EC2::Subnet")] if not subnets else [self.cf_ref(s) for s in subnets]
        security_groups = [self.cf_ref(s) for s in self.get_all(
            "AWS::EC2::SecurityGroup")] if not security_groups else [self.cf_ref(s) for s in security_groups]
        vpc = self.get_first("AWS::EC2::VPC")
        vpc_ref = self.cf_ref(vpc)
        required = {
            "Listeners": list
        }

        optional = {
            "AccessLoggingPolicy": dict,
            "AppCookieStickinessPolicy": list,
            "AvailabilityZones": list,
            "ConnectionDrainingPolicy": dict,
            "ConnectionSettings": dict,
            "CrossZone": bool,
            "HealthCheck": dict,
            "Instances": list,
            "LBCookieStickinessPolicy": list,
            "LoadBalancerName": str,
            "Policies": list,
            "Scheme": str,
            "SecurityGroups": list,
            "Subnets": list,
            "Tags": list
        }
        self.add_resource(name,
                          "AWS::ElasticLoadBalancing::LoadBalancer",
                          required,
                          optional,
                          Listeners=listeners,
                          CrossZone=cross_zone,
                          depends=[vpc] + self.get_all("AWS::EC2::Subnet"),
                          SecurityGroups=security_groups,
                          Subnets=subnets)

    def add_autoscaling_group(self, name, max_size="1", min_size="0", subnets=None, instance=None, launch_config=None, **kwargs):
        subnets = [self.cf_ref(s) for s in self.get_all(
            "AWS::EC2::Subnet")] if not subnets else [self.cf_ref(s) for s in subnets]
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
            "LoadBalancerNames": list,
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
                              LaunchConfigurationName=self.cf_ref(launch_config),
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
                              InstanceId=self.cf_ref(instance),
                              **kwargs
                              )

    def add_user(self, name, **kwargs):
        required = {}
        optional = {
            "Groups": list,
            "LoginProfile": str,
            "ManagedPolicyArns": list,
            "Path": str,
            "Policies": list,
            "UserName": str
        }
        self.add_resource(name,
                          "AWS::IAM::User",
                          required,
                          optional,
                          UserName=name,
                          **kwargs
                          )

    def add_role(self, name, assume_policy=None, **kwargs):
        required = {
            "AssumeRolePolicyDocument": dict
        }
        optional = {
            "RoleName": str,
            "ManagedPolicyArns": list,
            "Path": str,
            "Policies": list,
            "UserName": str
        }
        if not assume_policy:
            assume_policy = {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {
                           "Service": ["ec2.amazonaws.com"]
                    },
                    "Action": ["sts:AssumeRole"]
                }]
            }

        self.add_resource(name,
                          "AWS::IAM::Role",
                          required,
                          optional,
                          RoleName=name,
                          AssumeRolePolicyDocument=assume_policy,
                          **kwargs
                          )

    def add_instance_profile(self, name, path="/", roles=None, **kwargs):
        required = {
            "Path": str,
            "Roles": list
        }
        optional = {}
        if not roles:
            roles = [self.cf_ref(role) for role in self.get_all("AWS::IAM::Role")]
        self.add_resource(name,
                          "AWS::IAM::InstanceProfile",
                          required,
                          optional,
                          Path=path,
                          Roles=roles
                          )
