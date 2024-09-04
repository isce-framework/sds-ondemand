#!/bin/bash
aws s3 cp ./usage-history.csv "s3://${ACTIVITY_TRACKER_BUCKET}/Ondemand_Logs/Activity_Tracker/usage-history.csv"
aws s3 cp ./email-history.csv "s3://${ACTIVITY_TRACKER_BUCKET}/Ondemand_Logs/Activity_Tracker/email-history.csv"
