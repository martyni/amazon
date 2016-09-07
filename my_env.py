from pprint import pprint
from amazon_cf import Environment
from amazon_client import Cloudformation
from helper import (
    Listener,
    SecurityGroupRules,
    UserPolicy,
    get_my_ip,
    ContainerDefinition
)

if __name__ == "__main__":
    # Manually created key called id_rsa in amazon console
    key_name = 'id_rsa'
    filename = 'file.json'
    stack_name = 'test'
    server_size = "t2.micro"
    ami = "ami-64385917"
    my_ip = get_my_ip()
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
    in_rules.add_rule("tcp", from_port=22, to_port=22, cidr_ip=my_ip)
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
    my_env.add_role("MytUser", Policies=docker_user.policies)
    my_env.add_instance_profile("My profile")
    my_env.add_launch_configuration(
        "my launch configuration", ami, server_size, KeyName=key_name, AssociatePublicIpAddress=True, IamInstanceProfile=my_env.cf_ref("MyProfile"))
    listener_80 = Listener(80, 80)
    my_env.add_loadbalancer("My Load Balancer", [ listener_80.get_listener() ])
    my_env.add_autoscaling_group("My Autoscaling Group", DesiredCapacity="1", LoadBalancerNames=[
                                 my_env.cf_ref("MyLoadBalancer")])
    container_kwargs = {
                "Name": "httpd",
                "Image": "httpd",
                "Cpu": 1,
                "PortMappings": [
                    {
                        "Protocol": "tcp",
                        "ContainerPort": 80,
                        "HostPort": 80
                    }
                ],
                "Memory": 128,
                "Essential": True
            }
    my_container = ContainerDefinition(**container_kwargs)
    my_env.add_ecs_task( 'web service', container_definitions=[ my_container.return_container() ] )
    my_env.add_ecs_service('web service running')

    # Launch stack
    pprint(my_env.show_resources())
    my_env.write_resources(filename)
    my_client = Cloudformation(stack_name, filename)
    my_client.create_stack()
