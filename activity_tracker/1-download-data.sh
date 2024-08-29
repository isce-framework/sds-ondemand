#!/bin/bash
aws s3 cp s3://nisar-st-data-ondemand/Ondemand_Logs/Activity_Tracker/usage-history.csv ./usage-history.csv
aws s3 cp s3://nisar-st-data-ondemand/Ondemand_Logs/Activity_Tracker/email-history.csv ./email-history.csv
