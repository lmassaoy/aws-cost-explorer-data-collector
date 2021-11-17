#!/usr/bin/env bash
DEST_BUCKET=""
PROFILE=""
PARAMETERS="cloudformation/cloudformation_parameters.json"
STACK_NAME="AWS-Cost-Explorer-Data-Collector"
REGION='us-east-1'

if [ -z "$1" ]
  then
    echo "No destination bucket provided. Setting the bucket to: " $DEST_BUCKET
  else
    echo "Setting the destination to: " $1
    DEST_BUCKET=$1
fi

if [ -z "$2" ]
  then
    echo "No profile provided. Setting the profile to: " $PROFILE
  else
    echo "Setting the profile to: " $2
    PROFILE=$2
fi

if [ -z "$3" ]
  then
    echo "No parameters file provided. Setting the parameters file to: " $PARAMETERS
  else
    echo "Setting the parameters to: " $3
    PARAMETERS=$3
fi

if [ -z "$4" ]
  then
    echo "No stack name provided. Setting the stack name to: " $STACK_NAME
  else
    echo "Setting the stack name to: " $4
    STACK_NAME=$4
fi

if [ -z "$5" ]
  then
    echo "No region provided. Setting the region to: " $REGION
  else
    echo "Setting the region to: " $5
    REGION=$5
fi

echo ''

echo 'Deployng the solution stack'
aws cloudformation deploy \
    --template-file cloudformation/data-collector.packaged.yaml\
    --s3-bucket $DEST_BUCKET \
    --parameter-overrides file://$PARAMETERS \
    --stack-name $STACK_NAME \
    --capabilities CAPABILITY_NAMED_IAM \
    --region $REGION \
    --profile $PROFILE