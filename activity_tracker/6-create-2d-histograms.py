#!/usr/bin/env python

# Saves 2 2-D histograms

from collections import namedtuple
import csv
import datetime
import pathlib

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as colors
import matplotlib as mpl

FIELD_NAMES = ['time', 'username', 'user_email', 'last_activity', 'started', 'type']
DATA_GAP_THRESHOLD = 3600  # if timestamp jumps by this many seconds, reset inactivity periods
HISTORY_FILENAME = 'usage-history.csv'
COLORS_FILENAME = 'colors.py'
FIGURE_DIRNAME = 'plots'
DURATION_LOG_BASE = 10
DURATION_NUM_BINS = 20
COUNT_LOG_BASE = 10
TIMEZONE_ADJUSTMENT = -7  # from UTC
TIMEZONE_NAME = "PDT"
TIMEZONE = datetime.timezone(datetime.timedelta(hours=TIMEZONE_ADJUSTMENT), TIMEZONE_NAME)
HOURS_PER_DAY = 24
DAYS_PER_WEEK = 7

InactivityPeriod = namedtuple('InactivityPeriod', ['username', 'instance_start', 'start'])

def plot_duration_vs_day_of_week(x, y):
    # Calculate logarithmically spaced bins for the y-axis using np.geomspace
    x_bins = np.linspace(0, DAYS_PER_WEEK, DAYS_PER_WEEK + 1)
    y_bins = np.geomspace(y.min(), y.max(), 20)

    plt.hist2d(x, y, bins=[x_bins, y_bins], cmap='viridis')
    plt.colorbar(label='Count')
    plt.yscale('log')
    def format_func(value, tick_number):
        return ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][int(value)]

    plt.gca().xaxis.set_major_formatter(mpl.ticker.FuncFormatter(format_func))
    plt.xticks(np.linspace(0, DAYS_PER_WEEK, DAYS_PER_WEEK, endpoint=False))
    plt.xlabel(f'Day of Week')
    plt.ylabel('Duration of Inactivity (hours)')
    plt.title('Hours of Inactivity vs. Inactivity Start Day')
    plt.savefig('plots/day_of_week.png')
    print(f"2D Histogram saved to {pathlib.Path.cwd() / 'plots' / 'day_of_week.png'}")
    plt.clf()

def plot_duration_vs_time_of_day(x, y):
    # Calculate logarithmically spaced bins for the y-axis using np.geomspace
    x_bins = np.linspace(0, HOURS_PER_DAY, HOURS_PER_DAY + 1)
    y_bins = np.geomspace(y.min(), y.max(), 25)

    plt.hist2d(x, y, bins=[x_bins, y_bins], cmap='viridis')
    plt.colorbar(label='Count')
    plt.yscale('log')
    plt.xticks(np.linspace(0, HOURS_PER_DAY, HOURS_PER_DAY // 4 + 1))
    plt.xlabel(f'Time of Day (hours past midnight {TIMEZONE_NAME})')
    plt.ylabel('Duration of Inactivity (hours)')
    plt.title('Hours of Inactivity vs. Inactivity Start Time')
    plt.savefig('plots/time_of_day.png')
    print(f"2D Histogram saved to {pathlib.Path.cwd() / 'plots' / 'time_of_day.png'}")
    plt.clf()


def get_username_to_period_to_duration(reader: csv.DictReader) -> dict[str, dict[InactivityPeriod, int]]:
    username_to_period_to_duration: dict[str, dict[InactivityPeriod, int]] = {}
    prev_time: int | None = None
    prev_periods: list[InactivityPeriod] = []
    for row in reader:
        time = int(row['time'])
        if prev_time is not None:
            if time < prev_time:
                time_column_ordinal = ordinal(FIELD_NAMES.index('time') + 1)
                raise ValueError(f"error: {HISTORY_FILENAME} must be sorted in order of increasing time ({time_column_ordinal} column)")
            if time - prev_time >= DATA_GAP_THRESHOLD:
                prev_periods.clear()
        if prev_time is None or time != prev_time:
            for period in prev_periods:
                if period.username not in username_to_period_to_duration:
                    username_to_period_to_duration[period.username] = {}
                username_to_period_to_duration[period.username][period] = time - period.start
            prev_periods.clear()
            prev_time = time
        prev_periods.append(InactivityPeriod(
            username=row['username'],
            instance_start=int(row['started']),
            start=int(row['last_activity'])
        ))
    return username_to_period_to_duration


def ordinal(n: int) -> str:
    suffixes = ('th', 'st', 'nd', 'rd') + ('th',) * 10
    index = n % 100
    if index > 13:
        return f'{n}{suffixes[index % 10]}'
    else:
        return f'{n}{suffixes[index]}'


figure_dir = pathlib.Path.cwd() / FIGURE_DIRNAME
figure_dir.mkdir(parents=True, exist_ok=True)
with open(HISTORY_FILENAME, newline='') as history_file:
    reader = csv.DictReader(history_file, fieldnames=FIELD_NAMES)
    username_to_period_to_duration = get_username_to_period_to_duration(reader)

times_of_day = []
days_of_week = []
durations = []
for period_to_duration in username_to_period_to_duration.values():
    filtered_period_to_duration = {period: duration for period, duration in period_to_duration.items() if duration > 15*60}
    times_of_day.extend(((period.start + TIMEZONE_ADJUSTMENT * 60*60) % (24*60*60)) / (60*60) for period in filtered_period_to_duration)
    days_of_week.extend(datetime.datetime.fromtimestamp(period.start, TIMEZONE).weekday() for period in filtered_period_to_duration)
    durations.extend(duration / (60*60) for duration in filtered_period_to_duration.values())

times_of_day = np.array(times_of_day)
days_of_week = np.array(days_of_week)
durations = np.array(durations)

plot_duration_vs_time_of_day(times_of_day, durations)
plot_duration_vs_day_of_week(days_of_week, durations)