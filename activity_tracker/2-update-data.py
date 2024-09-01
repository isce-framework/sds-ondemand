#!/usr/bin/env python

"""Tracks the activity of OnDemand users."""
from datetime import datetime, timedelta
from collections import namedtuple
import csv
import os
import requests
import boto3
import subprocess

# General Settings
inactive_hours_limit = 3                                 # If idle time reaches this limit, jenkins will flag user as inactive
idle_email_hour_user = [ 3, 6, 12, 16, 24, 48,
                         72, 96, 120, 144,
                         168, 192, 216, 240,
                         264, 288, 312, 335 ]            # If idle time reaches one of these intervals, then idle email notification sent to user
idle_email_hour_ondemand_slack = 96                      # If idle time reaches this value, email sent to sds-ondemand slack channel to get ondemand team to investigate

# JupyterHub API Settings
ODS_ACTV_URL = 'https://nisar.jpl.nasa.gov/ondemand/hub/api/users'
TOKEN = os.environ['JUPYTERHUB_AUTH_KEY']
SERVER_TIMESTAMP_SPLIT_FORMAT = '%Y-%m-%dT%H:%M:%S'
TIMESTAMP_FORMAT = SERVER_TIMESTAMP_SPLIT_FORMAT

# AWS Settings for cognito
USER_POOL_ID = os.environ['COGNITO_USER_POOL_ID']
AWS_REGION = os.environ['COGNITO_AWS_REGION']

# Usage history settings
USAGE_HIST_FIELD_NAMES = ['time', 'username', 'user_email', 'last_activity', 'started', 'type']
USAGE_HIST_FILE = 'usage-history.csv'

# Email history settings
EMAIL_HIST_FIELD_NAMES = ['username', 'instance_start', 'inactivity_start', 'inactive_hours']
EMAIL_HIST_FILE = 'email-history.csv'

INACTIVITY_NOTIF_HELP_EMAIL = os.environ['INACTIVITY_NOTIF_HELP_EMAIL']
InstanceSnapshot = namedtuple('InstanceSnapshot', USAGE_HIST_FIELD_NAMES)

class UserNotFoundError(Exception):
    pass

class NoEmailAssociatedError(Exception):
    pass

# Main Function
def main() -> None:
    # JupyterHub API request for user status list
    payload = requests.get(ODS_ACTV_URL, headers={'Authorization': f'token {TOKEN}'},
            params={'state': 'active','include_stopped_servers': False})
    now = datetime.now()
    
    formatted_time = str(now.strftime(TIMESTAMP_FORMAT))
    print('\n=================================================================')
    print('Current Time(UTC): ' + formatted_time)
    print('=================================================================\n')
    
    snapshots = get_snapshots(payload, now)
    
    flagged_servers = []
    server_types = []
    
    # Parse JupyterHub API return payload
    for snapshot in snapshots:
        # Calculate how long instance has been active
        active_elapsed = snapshot.time - snapshot.last_activity
        inactive_hours = active_elapsed // 3600

        # Calculate how long instance has been started
        started_elapsed = snapshot.time - snapshot.started
        started_hours = started_elapsed // 3600

        # Update server type list
        if snapshot.type not in server_types:
            server_types.append(snapshot.type)

        # Store idle user information
        if inactive_hours >= inactive_hours_limit:
            flagged_servers.append({
                'snapshot': snapshot,
                'username': snapshot.username,
                'user_email': snapshot.user_email,
                'last_activity': format_timestamp(snapshot.last_activity),
                'inactive_hours': inactive_hours,
                'started': format_timestamp(snapshot.started),
                'started_hours': started_hours,
                'type': snapshot.type if snapshot.type is not None else "Unknown",
            })

        # Print Parsed Logged-in User Status List Section to console
        print(snapshot.username)
        print(f'\tUser Email: {snapshot.user_email}')
        print(f'\tInstance Type: {snapshot.type}')
        print(f'\tLast Activity: {format_timestamp(snapshot.last_activity)} ({inactive_hours}h ago)')
        print(f'\tStarted: {format_timestamp(snapshot.last_activity)} ({started_hours}h ago)')
        with open(USAGE_HIST_FILE, 'a', newline='') as history_file:
            writer = csv.DictWriter(history_file, fieldnames=USAGE_HIST_FIELD_NAMES)
            writer.writerow(snapshot._asdict())
    
    # Print Idle User Report Section
    print('\n=================================================================\n\nLong Inactive Servers (>='+ str(inactive_hours_limit) + 'hr):')
    for server_type in server_types:
        prefix = 'GPU' if 'gpu' in server_type.lower() else 'CPU'
        print(f'\n{prefix} Servers ({server_type}):')
        for item in flagged_servers:
            if item['type'] == server_type:
                # Print Idle User Report to console
                print(f'\t- {item["username"]} | {item["user_email"] if item["user_email"] is not None else "Email address not found"} | ({item["inactive_hours"]}h ago)')
                
                # Send Email Idle Notification to Users at set intervals but only send email to ondemand-help if limit reached
                if not emails_sent(username=item["username"], instance_start=item["snapshot"].started, inactivity_start=item["snapshot"].last_activity, inactive_hours=item["inactive_hours"]):
                    if item["inactive_hours"] in idle_email_hour_user:
                        if item["user_email"] is not None:
                            send_idle_email(item["username"],item["user_email"], item['type'], item["last_activity"], item["inactive_hours"], item["started"], item['started_hours'])
                        send_idle_email(item["username"], os.environ['WARNING_COPY_EMAIL'], item['type'], item["last_activity"], item["inactive_hours"], item["started"], item['started_hours'])
                    elif item["inactive_hours"] == idle_email_hour_ondemand_slack:
                        send_idle_email_ondemand_help(item["username"], os.environ['SLACK_EMAIL'], item['type'], item["last_activity"], item['inactive_hours'], item["started"], item['started_hours'])
                    register_emails_as_sent(username=item["username"], instance_start=item["snapshot"].started, inactivity_start=item["snapshot"].last_activity, inactive_hours=item["inactive_hours"])

    print('\n\n')

    return 0

def emails_sent(username, instance_start, inactivity_start, inactive_hours):
    with open(EMAIL_HIST_FILE, newline='') as email_hist_file:
        reader = csv.DictReader(email_hist_file, fieldnames=EMAIL_HIST_FIELD_NAMES)
        for row in reader:
            if (row['username'] == username and
                    int(row['instance_start']) == instance_start and
                    int(row['inactivity_start']) == inactivity_start and
                    int(row['inactive_hours']) == inactive_hours):
                return True
        return False

def register_emails_as_sent(username, instance_start, inactivity_start, inactive_hours):
    with open(EMAIL_HIST_FILE, 'a', newline='') as email_hist_file:
        writer = csv.DictWriter(email_hist_file, fieldnames=EMAIL_HIST_FIELD_NAMES)
        writer.writerow({'username': username,
                         'instance_start': instance_start,
                         'inactivity_start': inactivity_start,
                         'inactive_hours': inactive_hours})

def get_snapshots(payload, time: datetime) -> list[InstanceSnapshot]:
    snapshots = []
    for item in payload.json():
        server_data = item['servers']['']

        active_ts = parse_server_timestamp(server_data['last_activity'])
        started_ts = parse_server_timestamp(server_data['started'])
        server_type = server_data['user_options'].get('profile', None)
        try:
            email = get_user_email(item['name'])
        except (UserNotFoundError, NoEmailAssociatedError):
            email = None
        
        snapshots.append(InstanceSnapshot(
            time=get_timestamp(time),
            username=item['name'],
            user_email=get_user_email(item['name']),
            last_activity=get_timestamp(active_ts),
            started=get_timestamp(started_ts),
            type=server_type
        ))
    return snapshots

def parse_server_timestamp(server_timestamp: str) -> datetime:
    return datetime.strptime(server_timestamp.split('.')[0], SERVER_TIMESTAMP_SPLIT_FORMAT)

# Function to send idle email notification to user
def send_idle_email(username, user_email, server_type, last_activity, inactive_hours, started, started_hours):
    result = subprocess.Popen(f'echo -e "\
This is an automated notification to indicate that your NISAR Ondemand \
Science account below has a Jupyter instance that has been idling for \
{inactive_hours} hr(s): \n\
    - Username: {username} \n\
    - Instance Type: {server_type} \n\
    - Last Activity: {last_activity} [{inactive_hours}hr(s) ago] \n\
    - Started: {started} [{started_hours}hr(s) ago] \n\
\n\
If this was intentional because you were running a background process, then \
this is fine to leave up. Be aware that the system will automatically shutdown \
your instance after 14 days (336 hrs) of idling. \
However, if you just forgot to shutdown your instance, then please log in \
and shutdown your instance via the hub control panel because there is AWS \
EC2 costs charged hourly. Please help us miminize cloud cost so we may continue \
to provide the NISAR Ondemand Science service. \n\
\n\
Reminder on how to shutdown your instance: \n\
    1. Log into the NISAR Ondemand Science system via-> https://nisar.jpl.nasa.gov/ondemand \n\
    2. Click File -> Hub Control Panel \n\
    3. Click \"Stop my server\" \n\
\n\
********************************************************************************************** \n\
* This is an automated email notification system. Do not reply back to this email as this inbox is not monitored. \n\
* If you have questions, please email the {INACTIVITY_NOTIF_HELP_EMAIL} address for assistance.                 \n\
********************************************************************************************** \
" \
| mailx -s "NISAR Science Ondemand Instance Idle Notification" \
{user_email}', \
                 shell=True, \
                 stdout=subprocess.PIPE)
    output, errors = result.communicate()

# Function to send idle email notification to ondemand-help to investigate long running idle users
def send_idle_email_ondemand_help(username, user_email, server_type, last_activity, inactive_hours, started, started_hours):
    result = subprocess.Popen(f'echo -e "\
This is an automated notification to indicate that the NISAR Ondemand \
Science account below has been idling for {inactive_hours} hr(s): \n\
    - Username: {username} \n\
    - Instance Type: {server_type} \n\
    - Last Activity: {last_activity} [{inactive_hours}hr(s) ago] \n\
    - Started: {started} [{started_hours}hr(s) ago] \n\
\n\
It is suggested that someone from the ondemand-help team reach out \
to the user directly to investigate account idling or log into their \
account to exam if there are background processes running to determine if it \
should be shut it down by an admin. \
\n\
********************************************************************************************** \n\
* This is an automated email notification system. Do not reply back to this email as this inbox is not monitored. \n\
* If you have questions, please email the {INACTIVITY_NOTIF_HELP_EMAIL} address for assistance.                 \n\
********************************************************************************************** \
" \
| mailx -s "NISAR Science Ondemand Instance Idle Notification" \
{user_email}', \
                 shell=True, \
                 stdout=subprocess.PIPE)
    output, errors = result.communicate()

# Function to get user email address using AWS cognito API 
def get_user_email(username):
    # Initialize Cognito client
    client = boto3.client('cognito-idp', region_name=AWS_REGION)

    try:
        # Call admin_get_user to get user information
        response = client.admin_get_user(
            UserPoolId=USER_POOL_ID,
            Username=username
        )

        # Extract user attributes
        for attr in response['UserAttributes']:
            if attr['Name'] == 'email':
                return attr['Value']
        
        # If email attribute is not found
        raise NoEmailAssociatedError()
    
    except client.exceptions.UserNotFoundException:
        raise UserNotFoundError()
        

def get_timestamp(dt: datetime) -> int:
	return int(datetime.timestamp(dt))

def format_timestamp(ts: int) -> str:
	return datetime.fromtimestamp(ts).strftime(TIMESTAMP_FORMAT)

# Entry point of script
main()
