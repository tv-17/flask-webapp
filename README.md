# Deploying a simple webapp to AWS

## AWS Infrastructure
### The webapp is hosted on multiple ec2 instances behind an elastic load balancer. S3 is being leveraged as a location for serving the most up to date version of the source code for the app.

 
## Deployment
### Deploying the infrastructure follows the principles of Infrastructure as Code. The entire stack is written in troposphere (a python wrapper around native cloudformation). Using troposphere allows us to take advantage of the logic presented by a high level programming language (i.e. adding conditional logic and the ability to integrate with other application code).

make create_stack

- deploys asg
- latest copy of source code is pulled down by instances from s3
- userdata provisions instance by setting up apache, mod_wsgi
to serve webapp
- autoscaling actions
- adds cname alias to route53 record