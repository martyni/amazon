from pprint import pprint
from amazon_cf import Environment
from amazon_client import Cloudformation
from helper import (
   Listener,
   SecurityGroupRules,
   Resource,
   UserPolicy
)

if __name__ == "__main__":
    # Manually created key called id_rsa in amazon console
    key_name = 'id_rsa' 
    filename = 'file.json'
    stack_name = 'test'
    my_env = Environment('my_env')
    my_env.add_vpc("VPC")
    my_env.add_subnet("My first subnet", AvailabilityZone={
                      "Fn::Select": ["1", {"Fn::GetAZs": {"Ref": "AWS::Region"}}]})
    my_env.add_subnet("My second subnet", AvailabilityZone={
                      "Fn::Select": ["2", {"Fn::GetAZs": {"Ref": "AWS::Region"}}]})
    my_env.add_subnet("My third subnet", AvailabilityZone={
                      "Fn::Select": ["0", {"Fn::GetAZs": {"Ref": "AWS::Region"}}]})
    my_env.add_internet_gateway("internet gateway")
    my_env.attach_internet_gateway("Attach gateway")
    my_env.add_route_table("My default route table")
    my_env.add_default_internet_route("To the internet")
    my_env.add_subnet_to_route_table("add first subnet")
    my_env.add_subnet_to_route_table(
        "add second subnet", subnet="MySecondSubnet")
    my_env.add_subnet_to_route_table(
        "add third subnet", subnet="MyThirdSubnet")
    in_rules = SecurityGroupRules("SecurityGroupIngress")
    in_rules = SecurityGroupRules("SecurityGroupIngress")
    in_rules.add_rule("tcp", from_port=22, to_port=22, cidr_ip="0.0.0.0/0")
    in_rules.add_rule("tcp", from_port=80, to_port=80, cidr_ip="0.0.0.0/0")
    out_rules = SecurityGroupRules("SecurityGroupEgress")
    out_rules.add_rule("-1", cidr_ip="0.0.0.0/0")
    my_env.add_security_group(
        "My security group", in_rules.rules, out_rules.rules)
    docker_user = UserPolicy("docker")
    docker_user.add_statement([
        "ecr:*",
        "ecs:CreateCluster",
        "ecs:DeregisterContainerInstance",
        "ecs:DiscoverPollEndpoint",
        "ecs:Poll",
        "ecs:RegisterContainerInstance",
        "ecs:StartTelemetrySession",
        "ecs:Submit*",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
    ])    
    my_env.add_role("Dave", Policies=docker_user.policies)
    my_env.add_instance_profile("Default")
    my_env.add_launch_configuration(
        "my launch configuration", "ami-64385917", "t2.micro", KeyName=key_name, IamInstanceProfile=my_env.ref("Default"))
    listener_80 = Listener(80, 80)
    listener_22 = Listener(22, 22)
    my_env.add_loadbalancer("My load balancer", [ l.get_listener() for l in (listener_80, listener_22) ] )
    my_env.add_autoscaling_group("my autoscaling group", LoadBalancerNames=[ my_env.ref("MyLoadBalancer") ])
    #Launch stack
    pprint(my_env.show_resources())
    my_env.write_resources(filename)
    my_client = Cloudformation(stack_name, filename)
    my_client.create_stack()
