#!/usr/bin/env bash
DEST_BUCKET=''
PROFILE=''

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

echo 'Packaging the stack for the AWS Cost Explorer data collector'
aws cloudformation package \
    --template-file cloudformation/data-collector.yaml \
    --output-template-file cloudformation/data-collector.packaged.yaml \
    --s3-bucket $DEST_BUCKET \
    --profile $PROFILE