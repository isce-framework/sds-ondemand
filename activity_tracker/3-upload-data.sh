#!/bin/bash
aws s3 cp ./usage-history.csv s3://nisar-st-data-ondemand/Ondemand_Logs/Activity_Tracker/usage-history.csv
aws s3 cp ./email-history.csv s3://nisar-st-data-ondemand/Ondemand_Logs/Activity_Tracker/email-history.csv
