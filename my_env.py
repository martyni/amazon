from pprint import pprint
from amazon_cf import Environment
from amazon_client import Cloudformation
from helper import (
    Listener,
    SecurityGroupRules,
    UserPolicy,
    get_my_ip,
    get_local_variables,
    convert_to_aws_list,
    ContainerDefinition
)

if __name__ == "__main__":
    # Manually created items and constants
    key_name = 'id_rsa'
    filename = 'file.json'
    stack_name = 'dev'
    server_size = "t2.micro"
    ami = "ami-64385917"
    app_container = "martyni/app"
    nginx_container = "martyni/nginx"
    domain = "martyni.co.uk."
    ssl_cert = "arn:aws:acm:eu-west-1:526914317097:certificate/c162e6f8-3f40-4468-a03f-03f5c8d8ee63"
    container_size = 450
    environment_variables = [
        "AWS_DEFAULT_PROFILE",
        "MAIL_USERNAME",
        "MAIL_PASSWORD",
        "MAIL_DEFAULT_SENDER",
        "MAIL_SERVER",
        "MAIL_PORT",
        "MAIL_USE_SSL"
    ]
    # Container configuration
    app_container = {
        "Name": "app",
                "Image": app_container,
                "Cpu": container_size,
        "Memory": container_size,
        "Environment": get_local_variable(environment_variables),
        "Essential": True
    }
    nginx_container = {
        "Name": "nginx",
                "Image": nginx_container,
                "Cpu": container_size,
                "PortMappings": [
                    {
                        "Protocol": "tcp",
                        "ContainerPort": 80,
                        "HostPort": 80
                    }
                ],
        "Memory": container_size,
        "Environment": convert_to_aws(SITE=stack_name + "." + domain)
        "Links": ["app"],
        "Essential": True
    }
    # Healthcheck config
    healthcheck = {
        "HealthyThreshold": 2,
        "Interval": 10,
        "Target": "HTTP:80/",
        "Timeout": 5,
        "UnhealthyThreshold": 10
    }
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
    in_rules.add_rule("tcp", from_port=443, to_port=443, cidr_ip="0.0.0.0/0",)
    in_rules.add_rule("tcp", from_port=80, to_port=80, cidr_ip="0.0.0.0/0",)
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
    my_env.add_role(stack_name + "role", Policies=docker_user.policies)
    my_env.add_instance_profile("My profile")
    my_env.add_launch_configuration(
        "my launch configuration",
        ami,
        server_size,
        KeyName=key_name,
        AssociatePublicIpAddress=True,
        IamInstanceProfile=my_env.cf_ref("MyProfile")
    )
    l_443 = Listener(
        443,
        80,
        lb_protocol="HTTPS",
        inst_protocol="HTTP",
        ssl_certificate_id=ssl_cert
    )
    my_env.add_loadbalancer(
        "My Load Balancer",
        [l_443.get_listener()],
        HealthCheck=healthcheck)
    my_env.add_autoscaling_group("My Autoscaling Group", DesiredCapacity="1", LoadBalancerNames=[
                                 my_env.cf_ref("MyLoadBalancer")])
    app_container = ContainerDefinition(**app_container)
    nginx_container = ContainerDefinition(**nginx_container)
    my_env.add_ecs_task('web service',
                        container_definitions=[
                            app_container.return_container(),
                            nginx_container.return_container()
                        ]
                        )
    my_env.add_ecs_service('web service running')
    resource_record = [my_env.cf_get_at("MyLoadBalancer", "DNSName")]
    my_env.add_record_set(
        stack_name + "." + domain,
        _type="CNAME",
        depends=["MyLoadBalancer"],
        HostedZoneName=domain,
        TTL="300",
        ResourceRecords=resource_record
    )
    # Launch stack
    pprint(my_env.show_resources())
    my_env.write_resources(filename)
    my_client = Cloudformation(stack_name, filename)
    my_client.create_stack()
