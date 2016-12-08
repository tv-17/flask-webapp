from troposphere import Base64, Join
from troposphere import Parameter, Ref, Template
from troposphere.autoscaling import AutoScalingGroup
from troposphere.autoscaling import LaunchConfiguration
from troposphere.elasticloadbalancing import LoadBalancer
from troposphere.policies import AutoScalingReplacingUpdate, AutoScalingRollingUpdate, UpdatePolicy
from troposphere.ec2 import SecurityGroup, SecurityGroupRule, EBSBlockDevice, BlockDeviceMapping
from troposphere.elasticloadbalancing import ConnectionDrainingPolicy, HealthCheck, Listener


class WebApp(object):

    def __init__(self):
        self.t = Template()
        self.vpc_param, self.subnet1, self.subnet2 = self.add_params()
        self.elb_sg, self.autoscaling_sg = self.create_security_groups(self.vpc_param)
        self.load_balancer = self.create_elb(self.subnet1, self.subnet2, self.elb_sg)
        self.create_instance(self.subnet1, self.subnet2, self.load_balancer, self.autoscaling_sg)

    def add_params(self):
        vpc_param = self.t.add_parameter(Parameter(
            "VpcId",
            Type="String",
            Description="VPC ID for the app.",
            Default="vpc-1f04cf79"
        ))

        subnet1 = self.t.add_parameter(Parameter(
            "Subnet1",
            Type="String",
            Description="First VPC subnet ID for the app.",
            Default="subnet-757bf058"
        ))

        subnet2 = self.t.add_parameter(Parameter(
            "Subnet2",
            Type="String",
            Description="Second VPC subnet ID for the app.",
            Default="subnet-757bf058"
        ))

        return vpc_param, subnet1, subnet2

    def create_security_groups(self, vpc_param):

        elb_sg = self.t.add_resource(
            SecurityGroup(
                "ElbSg",
                GroupDescription="Allows inbound connection from from everywhere on port 80",
                VpcId=Ref(vpc_param),
                SecurityGroupIngress=[
                    SecurityGroupRule(
                        IpProtocol="tcp",
                        FromPort="80",
                        ToPort="80",
                        CidrIp="0.0.0.0/0",
                    )
                ],
                SecurityGroupEgress=[
                    SecurityGroupRule(
                        IpProtocol="tcp",
                        FromPort="1234",
                        ToPort="1234",
                        CidrIp="127.0.0.1",
                    )
                ]
            )
        )

        autoscaling_sg = self.t.add_resource(
            SecurityGroup(
                "AutoscalingSG",
                GroupDescription="Allows inbound connection from elb sg on port 80",
                VpcId=Ref(vpc_param),
                SecurityGroupIngress=[
                    SecurityGroupRule(
                        IpProtocol="tcp",
                        FromPort="80",
                        ToPort="80",
                        SourceSecurityGroupId=Ref(elb_sg),
                    )
                ],
                SecurityGroupEgress=[
                    SecurityGroupRule(
                        IpProtocol="tcp",
                        FromPort="1234",
                        ToPort="1234",
                        CidrIp="127.0.0.1",
                    )
                ]
            )
        )
        return elb_sg, autoscaling_sg

    def create_elb(self, subnet1, subnet2, elb_sg):
        load_balancer = self.t.add_resource(LoadBalancer(
            "LoadBalancer",
            ConnectionDrainingPolicy=ConnectionDrainingPolicy(
                Enabled=True,
                Timeout=120,
            ),
            Subnets=[Ref(subnet1), Ref(subnet2)],
            HealthCheck=HealthCheck(
                Target="HTTP:80/",
                HealthyThreshold="5",
                UnhealthyThreshold="2",
                Interval="20",
                Timeout="15",
            ),
            Listeners=[
                Listener(
                    LoadBalancerPort="80",
                    InstancePort="80",
                    Protocol="HTTP",
                ),
            ],
            CrossZone=True,
            SecurityGroups=[Ref(elb_sg)],
            LoadBalancerName="webapp-elb",
            Scheme="internet-facing",
        ))

        return load_balancer

    def create_instance(self, subnet1, subnet2, load_balancer, autoscaling_sg):

        launch_config = self.t.add_resource(LaunchConfiguration(
            "LaunchConfiguration",
            UserData=Base64(Join('', [
                "#!/bin/bash\n",
                "cfn-signal -e 0",
                "    --resource AutoscalingGroup",
                "    --stack ", Ref("AWS::StackName"),
                "    --region ", Ref("AWS::Region"), "\n"
            ])),
            ImageId="ami-b73b63a0",
            KeyName="thivancf",
            BlockDeviceMappings=[
                BlockDeviceMapping(
                    DeviceName="/dev/sda1",
                    Ebs=EBSBlockDevice(
                        VolumeSize="8"
                    )
                ),
            ],
            SecurityGroups=[Ref(autoscaling_sg)],
            InstanceType="t2.micro",
        ))

        self.t.add_resource(AutoScalingGroup(
            "AutoscalingGroup",
            DesiredCapacity=2,
            LaunchConfigurationName=Ref(launch_config),
            MinSize=1,
            MaxSize=4,
            VPCZoneIdentifier=[Ref(subnet1), Ref(subnet2)],
            LoadBalancerNames=[Ref(load_balancer)],
            HealthCheckType="EC2",
            UpdatePolicy=UpdatePolicy(
                AutoScalingReplacingUpdate=AutoScalingReplacingUpdate(
                    WillReplace=True,
                ),
                AutoScalingRollingUpdate=AutoScalingRollingUpdate(
                    PauseTime='PT5M',
                    MinInstancesInService="1",
                    MaxBatchSize='1',
                    WaitOnResourceSignals=True
                )
            )
        ))

        return launch_config

if __name__ == '__main__':
    template = WebApp()
    print template.t.to_json()