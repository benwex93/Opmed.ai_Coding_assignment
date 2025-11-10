import colorcet as cc
import seaborn as sns
from matplotlib import pyplot as plt
import sys
import pandas as pd

def plot_day_schedule(schedule):
    fig, ax = plt.subplots(nrows=1, ncols=1)
    fig.set_size_inches(w=2 * 9.5, h=2 * 5)
    fig.tight_layout(pad=1.7)

    resources = set(schedule['anesthetist_id'])
    resources = sorted(resources, key=lambda x: (len(x), x), reverse=True)
    resource_mapping = {resource: i for i, resource in enumerate(resources)}

    intervals_start = (schedule.start_time - schedule.start_time.dt.floor('d')).dt.total_seconds().div(3600)
    intervals_end = (schedule.end_time - schedule.start_time.dt.floor('d')).dt.total_seconds().div(3600)

    intervals = list(zip(intervals_start, intervals_end))

    palette = sns.color_palette(cc.glasbey_dark, n_colors=len(schedule))
    palette = [(color[0] * 0.9, color[1] * 0.9, color[2] * 0.9) for color in palette]
    cases_colors = {case_id: palette[i] for i, case_id in enumerate(set(schedule['room_id']))}

    for i, (resource_on_block_id, resource, evt) in enumerate(
            zip(schedule['room_id'], schedule['anesthetist_id'], intervals)):
        txt_to_print = str(i)
        ax.barh(resource_mapping[resource], width=evt[1] - evt[0], left=evt[0], linewidth=1, edgecolor='black',
                color=cases_colors[resource_on_block_id])
        ax.text((evt[0] + evt[1] - 0.07 * len(str(txt_to_print))) / 2, resource_mapping[resource], txt_to_print,
                name='Arial', color='white', va='center')

    ax.set_yticks(range(len(resources)))
    ax.set_yticklabels([f'{resource}' for resource in resources])

    ax.set_ylabel('anesthetist_id'.replace('_', ' '))

    ax.title.set_text(f'Total {len(set(schedule["anesthetist_id"]))} anesthetists')

    plt.show()

def main(solution_path):
    # Load the schedule (assuming CSV)
    schedule = pd.read_csv(solution_path, parse_dates=['start_time', 'end_time'])
    plot_day_schedule(schedule)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python script_name.py <path_to_schedule.csv>")
        sys.exit(1)

    solution_path = sys.argv[1]
    main(solution_path)