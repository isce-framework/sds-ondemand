#!/usr/bin/env python

# Saves 4 1-D histograms

import csv
from collections import namedtuple
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.colors as colors
import pathlib
import os
import numpy as np
import numpy.typing as npt
import datetime

FIELD_NAMES = ['time', 'username', 'user_email', 'last_activity', 'started', 'type']
INACTIVITY_THRESHOLDS = [(150, True, 'unfiltered.png'), (3*3600, False, 'filtered_by_user.png')]  # for each value, create a histogram including only durations at least that many seconds long
DATA_GAP_THRESHOLD = 3600  # if timestamp jumps by this many seconds, reset inactivity periods
HISTORY_FILENAME = 'usage-history.csv'
COLORS_FILENAME = 'colors.py'
FIGURE_DIRNAME = 'plots'
DURATION_LOG_BASE = 10
DURATION_NUM_BINS = 20
COUNT_LOG_BASE = 10

InactivityPeriod = namedtuple('InactivityPeriod', ['username', 'instance_start', 'start', 'is_gpu'])

def main() -> None:
    with open(COLORS_FILENAME) as colors_file:
        color_list = eval(colors_file.read())
    figure_dir = pathlib.Path.cwd() / FIGURE_DIRNAME
    figure_dir.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILENAME, newline='') as history_file:
        reader = csv.DictReader(history_file, fieldnames=FIELD_NAMES)
        username_to_period_to_duration = get_username_to_period_to_duration(reader)
    
    username_to_durations = {username: np.array(list(period_to_duration.values()), np.int64) for username, period_to_duration in username_to_period_to_duration.items()}
    for threshold, log_count, name in INACTIVITY_THRESHOLDS:
        filtered_username_to_durations = {username: durations[durations >= threshold] for username, durations in username_to_durations.items() if np.any(durations >= threshold)}
        if len(filtered_username_to_durations) > 0:
            figure_path = figure_dir / name
            if log_count:
                plot_histogram_unstacked(filtered_username_to_durations, figure_path)
            else:
                plot_histogram_stacked(filtered_username_to_durations, figure_path, color_list)
            print(f"Histogram saved to {figure_path}")
    
    filtered_username_to_durations = {username: durations[durations >= 3*3600] for username, durations in username_to_durations.items() if np.any(durations >= 3*3600)}
    username_to_filtered_period_to_duration = {username: {period: duration for period, duration in period_to_duration.items() if duration >= 3*3600} for username, period_to_duration in username_to_period_to_duration.items()}
    filtered_username_to_is_gpus = {username: np.array(list(period.is_gpu for period in period_to_duration), np.bool) for username, period_to_duration in username_to_filtered_period_to_duration.items()}
    username_to_is_gpus = {username: np.array(list(period.is_gpu for period in period_to_duration), np.bool) for username, period_to_duration in username_to_period_to_duration.items()}
    plot_histogram_instance_type(filtered_username_to_durations, filtered_username_to_is_gpus, figure_dir / 'filtered_by_type.png', log_count=False)
    print(f"Histogram saved to {figure_dir / 'filtered_by_type.png'}")
    plot_histogram_instance_type(username_to_durations, username_to_is_gpus, figure_dir / 'unfiltered_by_type.png', log_count=True)
    print(f"Histogram saved to {figure_dir / 'unfiltered_by_type.png'}")

    # The beginning of the inactivity period tells me when it starts.
    # But we don't need inactivity periods.
    # It can just be % active vs inactive
    # Actually, that's not ideal because ac
    # Beginning is more helpful for shutdown strategy because it's about when we detect inactivity.
    # Actually, we want the end as well. With both, we can see when inactivity tends to start as well as when it tends to end.
    # Specifically, when it tends to NOT end can tell us when we should shut it down. And how long it lasts when it starts can tell us stuff too.
    
    # username_to_start_to_duration = {username: {period.start: duration for period, duration in period_to_duration.items()} for username, period_to_duration in username_to_period_to_duration.items()}
    # plot_time_of_day(username_to_start_to_duration, figure_dir / 'colormap.png')
    # print(f"2D Histogram saved to {figure_dir / 'colormap.png'}")

def ts_to_day(ts):
    return datetime.datetime.fromtimestamp(ts).weekday()

def plot_time_of_day(username_to_start_to_duration, file_path):
    # TODO: start_to_duration is error-prone because there might be multiple
    # inactivity periods with the same start under the same user, but with different
    # instance_start (due to second-level data)
    DURATION_THRESHOLD = 150
    starts = []
    durations = []
    for start_to_duration in username_to_start_to_duration.values():
        for start, duration in start_to_duration.items():
            if duration >= DURATION_THRESHOLD and duration < 25000:  # TODO: remove 2nd condition
                starts.append(start % (24 * 60 * 60)) 
                durations.append(duration)

    x_bins = np.linspace(0, 24 * 60 * 60, 25) 
    y_bins = np.geomspace(DURATION_THRESHOLD, max(durations), 21) 

    plt.hist2d(starts, durations, bins=[x_bins, y_bins], cmap='viridis', norm=colors.LogNorm())
    plt.colorbar(label='Number of Inactivity Periods Plus 1')
    plt.yscale('log')
    plt.xlabel('Time of Day (seconds after midnight UTC)')
    plt.ylabel('Duration of Inactivity (seconds)')
    plt.title('Inactivity Durations vs. Start of Inactivity Period')
    plt.savefig(file_path)
    
    # heatmap, xedges, yedges = np.histogram2d(starts, durations, bins=(x_bins, y_bins))
    # heatmap += 1  # Otherwise, 0's show up as white.

    # fig, ax = plt.subplots()
    # im = ax.imshow(heatmap.T, origin='lower', cmap='hot', 
    #                extent=[xedges[0], xedges[-1], yedges[0], yedges[-1]],
    #                norm=colors.LogNorm())
    # fig.colorbar(im, ax=ax, label='Number of Inactivity Periods Plus 1')
    # # ax.set_yscale('log')
    # formatter = mpl.dates.DateFormatter('%H:%M')
    # ax.xaxis.set_major_formatter(formatter)
    # ax.set_xlabel('Time of Day')
    # ax.set_ylabel('Duration of Inactivity (seconds)')
    # ax.set_title('Inactivity Heatmap')
    
    # fig.savefig(file_path)

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
            start=int(row['last_activity']),
            is_gpu='gpu' in row['type'].lower()
        ))
    return username_to_period_to_duration


def custom_rounding(arr):
    # Convert input to numpy array if it's not already
    arr = np.asarray(arr)
    
    # Define rounding functions for different ranges
    def round_value(x):
        return x
        if x < 60:
            return np.round(x / 5) * 5
        elif x < 10 * 60:
            return np.round(x / 60) * 60
        elif x < 60 * 60:
            return np.round(x / (5 * 60)) * (5 * 60)
        elif x < 24 * 60 * 60:
            return np.round(x / (60 * 60)) * (60 * 60)
        else:
            return np.round(x / (24 * 60 * 60)) * (24 * 60 * 60)
    
    # Apply the rounding function element-wise
    vectorized_round_value = np.vectorize(round_value)
    return vectorized_round_value(arr)

def plot_histogram_instance_type(username_to_durations: dict[str, npt.NDArray[np.int64]], username_to_is_gpus: dict[str, npt.NDArray[np.bool]], file_path: pathlib.Path, log_count: bool = False) -> None:
    bins = np.geomspace(min(durations.min() for durations in username_to_durations.values()),
                        max(durations.max() for durations in username_to_durations.values()),
                        DURATION_NUM_BINS)
    durations = []
    is_gpus = []
    for username, user_durations in username_to_durations.items():
        durations.extend(user_durations)
        is_gpus.extend(username_to_is_gpus[username])
    durations = np.array(durations, np.int64)
    is_gpus = np.array(is_gpus, np.bool)

    # TODO: Add option to censor people's names, still including legend but with User 1, User 2, ...
    fig, ax = plt.subplots()
    ax.set_axisbelow(True)
    ax.grid(
        visible=True, which="major", linestyle="-", linewidth="0.5", color="black"
    )
    ax.grid(
        visible=True, which="minor", linestyle=":", linewidth="0.5", color="grey", axis='y'
    )
    
    gpu_kept = durations[is_gpus & (durations < 7.2*60*60)]
    cpu_kept = durations[np.logical_not(is_gpus) & (durations < 17*60*60)]
    gpu_removed = durations[is_gpus & (durations >= 7.2*60*60)]
    cpu_removed = durations[np.logical_not(is_gpus) & (durations >= 17*60*60)]

    gpu_sum = np.sum(gpu_removed)
    cpu_sum = np.sum(cpu_removed)
    gpu_rate = 3.06/60/60
    cpu_rate = 1.53/3/60/60
    gpu_saved = gpu_sum * gpu_rate
    cpu_saved = cpu_sum * cpu_rate
    total_saved = gpu_saved + cpu_saved

    ax.hist([gpu_kept, gpu_removed, cpu_kept, cpu_removed], bins=bins, label=['GPU kept', f'GPU removed (${gpu_saved:.2f})', 'CPU kept', f'CPU removed (${cpu_saved:.2f})'], color=['#1f77b4', 'green', '#ff7f0e', 'red'], stacked=True)
    # box = ax.get_position()
    # ax.set_position([box.x0, box.y0, box.width * 0.8, box.height])
    # ax.legend(bbox_to_anchor=(1.1, 1.0), fontsize='x-small')
    ax.legend()
    ax.set_xscale('log', base=DURATION_LOG_BASE)
    ax.set_xlabel('Inactivity duration')
    if log_count:
        ax.set_yscale('log', base=COUNT_LOG_BASE)
    ax.set_ylabel('Count')
    def format_func(value, tick_number):
        if value < 60:
            return f'{value:.1f} s'
        elif value < 60*60:
            return f'{value / 60:.1f} m'
        elif value < 24*60*60:
            return f'{value / (60*60):.1f} h'
        else:
            return f'{value / (24*60*60):.1f} d'

    ax.xaxis.set_major_formatter(mpl.ticker.FuncFormatter(format_func))
    ax.set_xticks(custom_rounding(np.geomspace(min(durations.min() for durations in username_to_durations.values()),
                        max(durations.max() for durations in username_to_durations.values()),
                        DURATION_NUM_BINS // 4)))
    ax.set_title(f'Long Inactivity Count vs. Duration (By Instance Type, ${total_saved:.2f})' if not log_count else f'Inactivity Count vs. Duration (By Instance Type, ${total_saved:.2f})')
    fig.savefig(file_path)

def plot_histogram_unstacked(username_to_durations: dict[str, npt.NDArray[np.int64]], file_path: pathlib.Path) -> None:
    durations = []
    for user_durations in username_to_durations.values():
        durations.extend(user_durations)
    durations = np.array(durations, np.int64)
    bins = np.geomspace(durations.min(), durations.max(), DURATION_NUM_BINS)
    fig, ax = plt.subplots()
    ax.set_axisbelow(True)
    ax.grid(
        visible=True, which="major", linestyle="-", linewidth="0.5", color="black"
    )
    ax.grid(
        visible=True, which="minor", linestyle=":", linewidth="0.5", color="grey", axis='y'
    )
    ax.hist(durations, bins=bins)
    ax.set_xscale('log', base=DURATION_LOG_BASE)
    ax.set_yscale('log', base=COUNT_LOG_BASE)
    ax.set_xlabel('Inactivity Duration')
    ax.set_ylabel('Count')
    def format_func(value, tick_number):
        if value < 60:
            return f'{value:.1f} s'
        elif value < 60*60:
            return f'{value / 60:.1f} m'
        elif value < 24*60*60:
            return f'{value / (60*60):.1f} h'
        else:
            return f'{value / (24*60*60):.1f} d'

    ax.xaxis.set_major_formatter(mpl.ticker.FuncFormatter(format_func))
    ax.set_xticks(custom_rounding(np.geomspace(durations.min(), durations.max(), DURATION_NUM_BINS // 4)))
    ax.set_title('Inactivity Count vs. Duration of Inactivity (Log Scale)')

    fig.savefig(file_path)

def plot_histogram_stacked(username_to_durations: dict[str, npt.NDArray[np.int64]], file_path: pathlib.Path, color_list: list[list[float]], censored: bool = False) -> None:
    bins = np.geomspace(min(durations.min() for durations in username_to_durations.values()),
                        max(durations.max() for durations in username_to_durations.values()),
                        DURATION_NUM_BINS)
    # TODO: Add option to censor people's names, still including legend but with User 1, User 2, ...
    fig, ax = plt.subplots()
    ax.set_axisbelow(True)
    ax.grid(
        visible=True, which="major", linestyle="-", linewidth="0.5", color="black"
    )
    ax.grid(
        visible=True, which="minor", linestyle=":", linewidth="0.5", color="grey", axis='y'
    )
    ax.hist(username_to_durations.values(), bins=bins, label=list(username_to_durations.keys()), color=color_list[:len(username_to_durations)], stacked=True)
    box = ax.get_position()
    ax.set_position([box.x0, box.y0, box.width * 0.8, box.height])
    ax.legend(bbox_to_anchor=(1.0, 1.0), fontsize='x-small')
    ax.set_xscale('log', base=DURATION_LOG_BASE)
    ax.set_xlabel('Inactivity duration')
    ax.set_ylabel('Count')
    def format_func(value, tick_number):
        if value < 60:
            return f'{value:.1f} s'
        elif value < 60*60:
            return f'{value / 60:.1f} m'
        elif value < 24*60*60:
            return f'{value / (60*60):.1f} h'
        else:
            return f'{value / (24*60*60):.1f} d'

    ax.xaxis.set_major_formatter(mpl.ticker.FuncFormatter(format_func))
    ax.set_xticks(custom_rounding(np.geomspace(min(durations.min() for durations in username_to_durations.values()),
                        max(durations.max() for durations in username_to_durations.values()),
                        DURATION_NUM_BINS // 4)))
    ax.set_title('Long Inactivity Count vs. Duration (By User)')

    fig.savefig(file_path)


def ordinal(n: int) -> str:
    suffixes = ('th', 'st', 'nd', 'rd') + ('th',) * 10
    index = abs(n) % 100
    if index > 13:
        return f'{n}{suffixes[index % 10]}'
    else:
        return f'{n}{suffixes[index]}'


main()
