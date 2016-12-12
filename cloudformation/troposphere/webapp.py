from troposphere import Base64, Join, GetAtt
from troposphere import Parameter, Ref, Template
from troposphere.autoscaling import AutoScalingGroup, LaunchConfiguration, ScalingPolicy
from troposphere.elasticloadbalancing import LoadBalancer
from troposphere.policies import AutoScalingReplacingUpdate, AutoScalingRollingUpdate, UpdatePolicy
from troposphere.ec2 import SecurityGroup, SecurityGroupRule, SecurityGroupEgress
from troposphere.elasticloadbalancing import ConnectionDrainingPolicy, HealthCheck, Listener
from troposphere.cloudwatch import Alarm, MetricDimension
from troposphere.route53 import RecordSetType, AliasTarget


class WebApp(object):

    def __init__(self):
        self.t = Template()
        self.vpc_param, self.subnet1, self.subnet2, self.webapp_zip = self.add_params()
        self.elb_sg, self.autoscaling_sg = self.create_security_groups(self.vpc_param)
        self.load_balancer = self.create_elb(self.subnet1, self.subnet2, self.elb_sg)
        self.create_instance(self.subnet1, self.subnet2, self.load_balancer, self.autoscaling_sg, self.webapp_zip)
        self.create_route53_records(self.load_balancer)

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
            Default="subnet-4ea6dc07"
        ))

        webapp_zip = self.t.add_parameter(Parameter(
            "WebappZip",
            Type="String",
            Description="Name of WebApp zip",
        ))

        return vpc_param, subnet1, subnet2, webapp_zip

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
                ]
            )
        )

        self.t.add_resource(SecurityGroupEgress(
            "ELBegress",
            DestinationSecurityGroupId=Ref(autoscaling_sg),
            GroupId=Ref(elb_sg),
            IpProtocol="-1",
            FromPort="-1",
            ToPort="-1"
        ))
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
                Target="TCP:80",
                HealthyThreshold="2",
                UnhealthyThreshold="9",
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

    def create_instance(self, subnet1, subnet2, load_balancer, autoscaling_sg, webapp_zip):

        launch_config = self.t.add_resource(LaunchConfiguration(
            "LaunchConfiguration",
            UserData=Base64(Join('', [
                "#!/bin/bash\n",
                "sudo yum install httpd mod_wsgi -y\n",
                "sudo pip install flask\n",
                "sudo chkconfig httpd on\n",
                "sudo service httpd start\n",
                "sudo service httpd restart\n",
                "sudo aws s3 cp s3://thivan-sample-data/", Ref(webapp_zip), " .\n",
                "sudo unzip ", Ref(webapp_zip), "\n",
                "sudo mv /home/ec2-user/app /var/www/html/\n",
                "sudo mv app /var/www/html/\n",
                "sudo mv /var/www/html/app/server_config/wsgi.conf /etc/httpd/conf.d/\n",
                "sudo groupadd group1\n",
                "sudo useradd user1 -g group1\n",
                "sudo usermod -a -G group1 apache\n",
                "sudo chown -vR :group1 /var/www/\n",
                "sudo chmod -vR g+w /var/www/\n",
                "sudo service httpd restart\n",
                "cfn-signal -e 0",
                "    --resource AutoscalingGroup",
                "    --stack ", Ref("AWS::StackName"),
                "    --region ", Ref("AWS::Region"), "\n"
            ])),
            IamInstanceProfile="arn:aws:iam::205198152101:instance-profile/webapps3",
            ImageId="ami-b73b63a0",
            KeyName="thivancf",
            SecurityGroups=[Ref(autoscaling_sg)],
            InstanceType="t2.micro",
        ))

        asg = self.t.add_resource(AutoScalingGroup(
            "AutoscalingGroup",
            DesiredCapacity=2,
            LaunchConfigurationName=Ref(launch_config),
            MinSize=1,
            MaxSize=4,
            VPCZoneIdentifier=[Ref(subnet1), Ref(subnet2)],
            LoadBalancerNames=[Ref(load_balancer)],
            HealthCheckGracePeriod=300,
            HealthCheckType="EC2",
            UpdatePolicy=UpdatePolicy(
                AutoScalingReplacingUpdate=AutoScalingReplacingUpdate(
                    WillReplace=True,
                ),
                AutoScalingRollingUpdate=AutoScalingRollingUpdate(
                    PauseTime='PT5M',
                    MinInstancesInService="1",
                    MaxBatchSize='1',
                )
            )
        ))

        scaling_policy = self.t.add_resource(ScalingPolicy(
            "ScalingPolicy",
            AdjustmentType="ChangeInCapacity",
            AutoScalingGroupName=Ref(asg),
            Cooldown="120",
            ScalingAdjustment="1"
        ))

        self.t.add_resource(Alarm(
            "CPUAlarm",
            EvaluationPeriods="1",
            Statistic="Maximum",
            Threshold="50",
            AlarmDescription="Alarm if CPU too high or metric disappears indicating instance is down",
            Period="60",
            AlarmActions=[Ref(scaling_policy)],
            Namespace="AWS/EC2",
            Dimensions=[
                MetricDimension(
                    Name="AutoScalingGroupName",
                    Value=Ref(asg)
                ),
            ],
            ComparisonOperator="GreaterThanThreshold",
            MetricName="CPUUtilization"
        ))
        return launch_config

    def create_route53_records(self, load_balancer):
        self.t.add_resource(RecordSetType(
            "ARecord",
            AliasTarget=AliasTarget(
                HostedZoneId=GetAtt(load_balancer, "CanonicalHostedZoneNameID"),
                DNSName=GetAtt(load_balancer, "DNSName")
            ),
            HostedZoneId="Z2XJ10AKMCBNEF",
            Comment="A Record Alias to ELB",
            Name="loremipsum.tv17.co.uk.",
            Type="A",
            DependsOn="LoadBalancer"
        ))

if __name__ == '__main__':
    template = WebApp()
    print template.t.to_json()
