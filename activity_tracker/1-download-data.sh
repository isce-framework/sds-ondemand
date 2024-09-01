#!/bin/bash
aws s3 cp "s3://${ACTIVITY_TRACKER_BUCKET}/Ondemand_Logs/Activity_Tracker/usage-history.csv" ./usage-history.csv
aws s3 cp "s3://${ACTIVITY_TRACKER_BUCKET}/Ondemand_Logs/Activity_Tracker/email-history.csv" ./email-history.csv
