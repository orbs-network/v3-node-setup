#!/bin/bash

# --- Quick script to create an EC2 instance with the correct specs and security group ---

read -p "Please enter your desired instance name: " instanceName

if [ -z "${instanceName}" ]; then
    echo "ERROR: instanceName cannot be empty"
    exit 1
fi

securityGroupId="sg-0445211f967de7058"

# You should not need to run these commands again, but just in case:
# aws ec2 create-security-group --group-name "luke-v3-test" --description "launch-wizard-7 created 2023-07-11T07:50:55.292Z" --vpc-id vpc-0588a7a72baea3102
# aws ec2 authorize-security-group-ingress --group-id ${securityGroupId} --protocol tcp --port 22 --cidr 0.0.0.0/0
# aws ec2 authorize-security-group-ingress --group-id ${securityGroupId} --protocol tcp --port 80 --cidr 0.0.0.0/0
# aws ec2 authorize-security-group-ingress --group-id ${securityGroupId} --protocol tcp --port 9100 --cidr 0.0.0.0/0

aws ec2 run-instances --image-id ami-053b0d53c279acc90 --count 1 --instance-type t2.xlarge --key-name v3-test --block-device-mappings '[{"DeviceName":"/dev/sda1", "Ebs":{"VolumeSize":30, "DeleteOnTermination":true, "VolumeType":"gp2", "SnapshotId":"snap-0d3283808e9f92122"}}]' --network-interfaces '[{"DeviceIndex":0, "AssociatePublicIpAddress":true, "Groups":["'${securityGroupId}'"]}]' --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value="'${instanceName}'"}]'


sleep 5

instancePublicIp=$(aws ec2 describe-instances --filters "Name=tag:Name,Values=${instanceName}" --query "Reservations[*].Instances[*].PublicIpAddress" --output text)

if [ -z "$instancePublicIp" ]; then
    echo "Connect to your instance ${instanceName} from the AWS console"
else
    sshConnectionString="ssh -i \"v3-test.pem\" ubuntu@${instancePublicIp}"
    echo "Use the following command to connect to your instance:"
    echo -e "\033[1m$sshConnectionString\033[0m"
fi