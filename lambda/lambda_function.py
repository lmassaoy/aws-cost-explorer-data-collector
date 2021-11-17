import os
import datetime
import pytz
import boto3
import pandas as pd
import numpy as np
import awswrangler as wr
from aws_lambda_powertools import Logger


ce_client = boto3.client('ce')
metrics = os.environ['METRICS'].split(';')
logger = Logger(service=os.environ['SERVICE_NAME'])
    
    
def get_yesterday_and_today():
    today = datetime.datetime.now().astimezone(pytz.timezone(os.environ['TIMEZONE']))
    yesterday = today - datetime.timedelta(days = 1) 
    return yesterday.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')


def treat_na_to_0(df_row):
    if df_row == 'N/A':
        return '0'
    else:
        return df_row


def request_tag_values(start_date,end_date,monitored_tag):
    response = ce_client.get_tags(
        TimePeriod={
            'Start': start_date,
            'End': end_date
        },
        TagKey=monitored_tag,
    )
    tags_results = response['Tags']
    
    while 'NextPageToken' in response:
        logger.info({'NextPageToken': response['NextPageToken']})
        response = ce_client.get_tags(
            TimePeriod={
                'Start': start_date,
                'End': end_date
            },
            TagKey=monitored_tag,
            NextPageToken=response['NextPageToken']
        )
        for tag in response['Tags']:
            tags_results.append(tag)
    
    return tags_results
    
    
def request_cost_and_usage(start_date,end_date,monitored_tag,tag_value):
    if tag_value is None:
        filter = {
                    'Tags': {
                        'Key': monitored_tag,
                        'MatchOptions': [
                            'ABSENT'
                        ]
                    }
                }
    else:
        filter = {
                    'Tags': {
                        'Key': monitored_tag,
                        'Values': [
                            tag_value,
                        ],
                        'MatchOptions': [
                            'EQUALS',
                        ]
                    }
                }

    response = ce_client.get_cost_and_usage(
        TimePeriod={
            'Start': start_date,
            'End': end_date
        },
        Granularity='DAILY',
        Filter=filter,
        Metrics=metrics,
        GroupBy=[
            {
                'Type': 'DIMENSION',
                'Key': 'SERVICE'
            },
        ]
    )
    daily_results = response['ResultsByTime']
    
    while 'NextPageToken' in response:
        logger.info({'NextPageToken': response['NextPageToken']})
        response = ce_client.get_cost_and_usage(
            TimePeriod={
                'Start': start_date,
                'End': end_date
            },
            Granularity='DAILY',
            Filter=filter,
            Metrics=metrics,
            GroupBy=[
                {
                    'Type': 'DIMENSION',
                    'Key': 'SERVICE'
                },
            ],
            NextPageToken=response['NextPageToken']
        )
        for day_result in response['ResultsByTime']:
            daily_results.append(day_result)
    
    return daily_results


@logger.inject_lambda_context(log_event=True)
def lambda_handler(event, context):
    # collects the period of data extraction requested
    if 'startDate' in event and 'endDate' in event:
        start_date = event['startDate']
        end_date = event['endDate']
    else:
        start_date, end_date = get_yesterday_and_today()

    pre_df = []
    monitored_tag = event['monitoredTag']
    
    # collects the existant values for the desired Tag
    tag_values = request_tag_values(start_date,end_date,monitored_tag)
    tag_values.remove('')

    # loops through the values found
    for tag_value in tag_values:
        daily_results = request_cost_and_usage(start_date,end_date,monitored_tag,tag_value)
            
        for daily_data in daily_results:
            for group in daily_data['Groups']:
                service_row = {
                    os.environ['DATE_COLUMN_NAME']: daily_data['TimePeriod']['Start'],
                    'startDate': daily_data['TimePeriod']['Start'],
                    'endDate': daily_data['TimePeriod']['End'],
                    'total': daily_data['Total'],
                    monitored_tag.lower(): tag_value,
                    'serviceName': group['Keys'][0]
                }
                for metric in metrics:
                    service_row[metric] = group['Metrics'][metric]
                pre_df.append(service_row)
    
    # collects the rest of the costs and put as 'uncategorized' data
    daily_results = request_cost_and_usage(start_date,end_date,monitored_tag,None)
    for daily_data in daily_results:
        for group in daily_data['Groups']:
            service_row = {
                os.environ['DATE_COLUMN_NAME']: daily_data['TimePeriod']['Start'],
                'startDate': daily_data['TimePeriod']['Start'],
                'endDate': daily_data['TimePeriod']['End'],
                'total': daily_data['Total'],
                monitored_tag.lower(): os.environ['UNCATEGORIZED_DATA'],
                'serviceName': group['Keys'][0]
            }
            for metric in metrics:
                service_row[metric] = group['Metrics'][metric]
            pre_df.append(service_row)

    # transforms into a pandas dataframe and handles datatypes
    df=pd.json_normalize(pre_df)
    df_schema=pd.io.json.build_table_schema(df)
    for field in df_schema['fields']:
        if 'Amount' in field['name']:
            df[field['name']] = df[field['name']].apply(treat_na_to_0)
            df[field['name']] = df[field['name']].fillna(0.0).astype(np.float64, errors='ignore')
        if 'Unit' in field['name']:
            df[field['name']] = df[field['name']].fillna('N/A').astype(str)

    if len(df.index) == 0:
        log_dict = {
            'message': 'The DataFrame is empty',
            'periodExtracted': {
                'startDate': start_date,
                'endDate': end_date,
            }
        }
        logger.info(log_dict)
        return {
            'statusCode': 404,
            'executionLog': log_dict
        }
        
    # writes into S3 as parquet files and creates/updates the Glue table
    wr.s3.to_parquet(
        df=df,
        path=f"s3://{os.environ['S3_BUCKET']}/{os.environ['S3_PATH']}",
        dataset=True,
        database=os.environ['GLUE_DB'],
        table=os.environ['GLUE_TABLE'],
        mode="overwrite_partitions",
        partition_cols=[os.environ['DATE_COLUMN_NAME']]
    )
    
    # logging the results
    log_dict = {
        'periodExtracted': {
            'startDate': start_date,
            'endDate': end_date,
        },
        'numberOfRowsWrittenIntoS3': len(df.index)
    }
    logger.info(log_dict)

    return {
        'statusCode': 200,
        'executionLog': log_dict
    }