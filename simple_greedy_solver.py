import pandas as pd
from datetime import datetime, timedelta
import heapq
import time

# ------------------ CONFIG ------------------
BUFFER_MINUTES = 15
MIN_SHIFT_HOURS = 5
MAX_SHIFT_HOURS = 12
OVERTIME_HOURS = 9
NUM_ROOMS = 20
# --------------------------------------------

def compute_cost(duration_hours):
    """Compute anesthesiologist cost based on rules."""
    base = max(MIN_SHIFT_HOURS, duration_hours)
    overtime = max(0, duration_hours - OVERTIME_HOURS)
    return base + 0.5 * overtime

def load_surgeries(csv_path):
    """Load and preprocess surgeries CSV."""
    df = pd.read_csv(csv_path)
    df['start'] = pd.to_datetime(df['start'])
    df['end'] = pd.to_datetime(df['end'])
    df['duration'] = df['end'] - df['start']
    df = df.sort_values('start').reset_index(drop=True)
    return df

def assign_rooms(df):
    """
    Assign surgeries to rooms.
    If no room is free at the surgery's start time,
    delay the surgery until the earliest room frees up.
    """
    # Min-heap of (end_time, room_id)
    room_heap = []
    room_counter = 0

    new_starts, new_ends, assigned_rooms = [], [], []

    for _, row in df.iterrows():
        start, duration = row['start'], row['duration']

        # Free up rooms that ended before 'start'
        while room_heap and room_heap[0][0] <= start:
            heapq.heappop(room_heap)

        if len(room_heap) < NUM_ROOMS:
            # Assign a new room (some free)
            room_id = f"room-{len(room_heap)}"
            actual_start = start
        else:
            # Wait until the earliest room is free
            earliest_end, room_id = heapq.heappop(room_heap)
            if earliest_end > start:
                actual_start = earliest_end
            else:
                actual_start = start

        actual_end = actual_start + duration
        heapq.heappush(room_heap, (actual_end, room_id))

        new_starts.append(actual_start)
        new_ends.append(actual_end)
        assigned_rooms.append(room_id)

    df['start'] = new_starts
    df['end'] = new_ends
    df['room_id'] = assigned_rooms
    df['duration_hours'] = (df['end'] - df['start']).dt.total_seconds() / 3600

    return df
def assign_anesthesiologists(df):
    """
    Assign anesthesiologists greedily to minimize idle gaps,
    ensuring no anesthesiologist works more than MAX_SHIFT_HOURS total.
    """
    anesthesiologists = []  # list of dicts: {id, shift_start, shift_end, last_room, total_hours}
    anesth_assignments = []
    anesth_counter = 0

    # iterate through surgeries
    for _, row in df.iterrows():
        start, end, room = row['start'], row['end'], row['room_id']
        duration_hours = (end - start).total_seconds() / 3600
        assigned = False

        for anesth in anesthesiologists:
            # Compute buffer if changing rooms
            buffer = timedelta(minutes=BUFFER_MINUTES if room != anesth['last_room'] else 0)

            # Check if anesthesiologist is available for this surgery
            if start >= anesth['shift_end'] + buffer:
                # Calculate new total shift if this surgery is added
                new_shift_end = end
                new_total = (new_shift_end - anesth['shift_start']).total_seconds() / 3600

                # If within 12-hour max shift
                if new_total <= MAX_SHIFT_HOURS:
                    anesth['shift_end'] = new_shift_end
                    anesth['last_room'] = room
                    anesth['total_hours'] = new_total
                    anesth_assignments.append(anesth['id'])
                    assigned = True
                    break  # stop searching once assigned

        if not assigned:
            # Create new anesthesiologist
            anesth_id = f"anesth-{anesth_counter}"
            anesth_counter += 1
            anesthesiologists.append({
                'id': anesth_id,
                'shift_start': start,
                'shift_end': end,
                'last_room': room,
                'total_hours': duration_hours
            })
            anesth_assignments.append(anesth_id)

    df['anesthetist_id'] = anesth_assignments
    return df

def compute_statistics(df):
    """Compute total cost and utilization."""
    stats = []
    for anesth_id, group in df.groupby('anesthetist_id'):
        start = group['start'].min()
        end = group['end'].max()
        shift_duration = (end - start).total_seconds() / 3600
        shift_duration = min(shift_duration, MAX_SHIFT_HOURS)
        cost = compute_cost(shift_duration)
        total_surgery_hours = group['duration_hours'].sum()
        stats.append((anesth_id, shift_duration, cost, total_surgery_hours))

    stats_df = pd.DataFrame(stats, columns=['anesth_id', 'shift_hours', 'cost', 'surgery_hours'])
    total_cost = stats_df['cost'].sum()
    utilization = stats_df['surgery_hours'].sum() / total_cost
    return total_cost, utilization, stats_df

def main():
    start_time = time.time()

    df = load_surgeries("surgeries.csv")
    df = assign_rooms(df)
    df = assign_anesthesiologists(df)

    total_cost, utilization, stats_df = compute_statistics(df)
    print(f"Total cost: {total_cost:.2f}")
    print(f"Utilization: {utilization * 100:.1f}%")
    print(f"Total anesthesiologists used: {df['anesthetist_id'].nunique()}")
    print(f"Total rooms used: {df['room_id'].nunique()}")

    # Rename final df columns
    df.rename(columns={'start': 'start_time', 'end': 'end_time'}, inplace=True)
    # Drop unused columns
    df = df.drop(['duration', 'duration_hours'], axis=1)
    # Reorder columns
    df = df[['Unnamed: 0', 'start_time', 'end_time', 'anesthetist_id', 'room_id']]

    filename = "simple_greedy_solution.csv"
    df.to_csv(filename, index=False)
    print(f"\nSaved solution to {filename}")
    print(df.head(10))

    end_time = time.time()
    elapsed = end_time - start_time
    print(f"\nTotal runtime: {elapsed:.2f} seconds")
if __name__ == "__main__":
    main()