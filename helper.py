
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
                try:
                   self.object[key] = kwargs[key] if type(kwargs[key]) == self.keys["All"][key] else self.exception(
                      '''{} is wrong format {} {}'''.format(key, type(kwargs[key]), self.keys["All"][key]))
                except BaseException:
                   if kwargs[key].get("Ref"):
                      self.object[key] = kwargs[key]

    def return_resource(self):
        self.resource = {"Type": self.type, "Properties": self.object}
        return self.resource 

class Listener(object):
   def __init__(self, instance_port, loadbalancer_port, policy_names=None, ssl_certificate_id=None, inst_protocol='TCP', lb_protocol='TCP'):
      self.instance_port = instance_port
      self.loadbalancer_port = loadbalancer_port
      self.policy_names = policy_names
      self.ssl_certificate_id = ssl_certificate_id
      self.lb_protocol = lb_protocol
      self.inst_protocol = inst_protocol

   def get_listener(self):
      obj = {
         "InstancePort" : str(self.instance_port),
         "InstanceProtocol" : self.inst_protocol,
         "LoadBalancerPort" : str(self.loadbalancer_port),
         "Protocol" : self.lb_protocol
      }
      if self.policy_names and type(self.policy_names) == list:
         obj["PolicyNames"] = self.policy_names

      if self.ssl_certificate_id and type(self.ssl_certificate_id) == str:
         obj["SSLCertificateId"] = self.ssl_certificate_id
      return obj


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

class UserPolicy(object):

   def __init__(self, name, version="2012-10-17"):
      self.version = version
      self.name = name
      self.counter = 0
      self.policies = []

   def add_statement(self, rules):
      statement = { 
                  "PolicyName" : self.name + str(self.counter),
                  "PolicyDocument": {
                     "Version": self.version,
                     "Statement": [ {
                        "Action" : rules,
                        "Effect" : "Allow",
                        "Resource" : "*"
                        }]
                     }
                  }
      self.counter += 1
      self.policies.append(statement)
      
