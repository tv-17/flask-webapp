# Deploying a simple WebApp to AWS

This repository contains the code for deploying a simple scalable web application hosted on Amazon Web Services (AWS).

## AWS Infrastructure
The WebApp is hosted on multiple EC2 instances within an AutoScaling group served by an Elastic Load Balancer. S3 is being leveraged as a location for serving the most up to date version of the source code for the app. A Route53 Cloudformation resource dynamically updates the CNAME Alias to point the ELB to a fixed DNS.

![Image of architecture on aws](/img/architecture.jpeg)

## Deployment and Scalability
Deploying the infrastructure follows the principles of Infrastructure as Code. The entire stack is written in [troposphere](https://github.com/cloudtools/troposphere) (a python library to create native cloudformation). Using troposphere allows us to take advantage of the logic presented by a high level programming language - python (i.e. adding conditional logic and the ability to integrate with other application code).
A combination of Flask, Apache and WSGI_MOD has been used to provide a scalable solution with provisioning achieved simply through UserData. AutoScaling actions combined with CloudWatch alarms ensures that instances will scale when hitting a predetermined CPU usage limit. 
The WebApp can be reached directly via the ELB or the DNS:

`loremipsum.tv17.co.uk`

### Examples of deployment:

The following command will launch the entire stack from scratch given a set of parameters (i.e. VPC ID & Subnet IDs). 
The command will also trigger the upload of the latest source code to S3 versioned via Git source control:

`make create_stack`

To deploy a change in source code to a stack that already exists the following command can be used:

`make update_stack`

To clean up all resources and delete the stack run:

`make delete_stack`



- userdata provisions instance by setting up apache, mod_wsgi
to serve webapp
- autoscaling actions
- adds cname alias to route53 record

![Image of architecture on aws](/img/architecture.jpeg)