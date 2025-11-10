# ortools_anesth_cost_model_with_utilization.py
import pandas as pd
from datetime import timedelta
from ortools.sat.python import cp_model
import time

SOLVER_TIME_LIMIT = 120  # seconds
NUM_ROOMS = 20
MAX_SHIFT_MINUTES = 12 * 60  # 12 hours

def read_surgeries(csv_path):
    df = pd.read_csv(csv_path)
    if 'id' not in df.columns:
        df = df.reset_index().rename(columns={'index': 'id'})
    df['start_dt'] = pd.to_datetime(df['start'])
    df['end_dt'] = pd.to_datetime(df['end'])
    origin = df['start_dt'].min().replace(hour=0, minute=0, second=0, microsecond=0)
    df['start_min'] = ((df['start_dt'] - origin).dt.total_seconds() / 60).astype(int)
    df['end_min'] = ((df['end_dt'] - origin).dt.total_seconds() / 60).astype(int)
    df['dur_min'] = (df['end_min'] - df['start_min']).astype(int)
    df = df.sort_values('start_min').reset_index(drop=True)
    return df, origin

def build_and_solve(df):
    model = cp_model.CpModel()
    n = len(df)
    max_anesth = n  # upper bound
    print(f"Building model with {n} surgeries...")

    # Surgery timing
    start, end, dur = [], [], []
    for i in range(n):
        s = model.NewIntVar(df.loc[i, 'start_min'], df.loc[i, 'start_min'], f"start_{i}")
        e = model.NewIntVar(df.loc[i, 'end_min'], df.loc[i, 'end_min'], f"end_{i}")
        d = int(df.loc[i, 'dur_min'])
        model.Add(e == s + d)
        start.append(s)
        end.append(e)
        dur.append(d)

    # --------------------------------------------
    # 1 Assign anesthesiologists
    # --------------------------------------------
    anesth_assigned = {}
    anesth_intervals = {a: [] for a in range(max_anesth)}

    for i in range(n):
        for a in range(max_anesth):
            b = model.NewBoolVar(f"an_{i}_{a}")
            anesth_assigned[(i, a)] = b
            iv = model.NewOptionalIntervalVar(start[i], dur[i], end[i], b, f"ival_an_{i}_{a}")
            # for each ANT add all possible intervals
            anesth_intervals[a].append(iv)
        # for surgery i only 1 of the following can be true: (i,1),(i,2),(i,3),... 
        model.AddExactlyOne([anesth_assigned[(i, a)] for a in range(max_anesth)])

    for a in range(max_anesth):
        model.AddNoOverlap(anesth_intervals[a])

    an_used = [model.NewBoolVar(f"an_used_{a}") for a in range(max_anesth)]
    for a in range(max_anesth):
        model.AddMaxEquality(an_used[a], [anesth_assigned[(i, a)] for i in range(n)])
        if a > 0:
            # makes sure to not use a later ANT when a previous one hasn't been used at all since will lead to unnecessary duplicate solution to search
            model.Add(an_used[a - 1] >= an_used[a])

    # --------------------------------------------
    # 2 Assign rooms (max 20)
    # --------------------------------------------
    room_assigned = {}
    room_intervals = {r: [] for r in range(NUM_ROOMS)}

    for i in range(n):
        for r in range(NUM_ROOMS):
            b = model.NewBoolVar(f"room_{i}_{r}")
            room_assigned[(i, r)] = b
            iv = model.NewOptionalIntervalVar(start[i], dur[i], end[i], b, f"ival_room_{i}_{r}")
            room_intervals[r].append(iv)
        model.AddExactlyOne([room_assigned[(i, r)] for r in range(NUM_ROOMS)])

    for r in range(NUM_ROOMS):
        model.AddNoOverlap(room_intervals[r])
    # --------------------------------------------
    # 15-minute buffer when anesthesiologist switches rooms
    # --------------------------------------------
    BUFFER = 15  # minutes

    # Only consider consecutive surgeries (end_i == start_j)
    pairs = [
        (i, j)
        for i in range(n)
        for j in range(n)
        if df.loc[j, 'start_min'] == df.loc[i, 'end_min']
    ]

    for a in range(max_anesth):
        for (i, j) in pairs:
            # Boolean: true if i and j assigned to same anesthesiologist
            # (this will be checked implicitly in the conditional)
            
            # Build linear expression for "same room" sum
            same_room_terms = []
            for r in range(NUM_ROOMS):
                both_same_r = model.NewBoolVar(f"both_room_{i}_{j}_{r}")
                model.AddBoolAnd([room_assigned[(i, r)], room_assigned[(j, r)]]).OnlyEnforceIf(both_same_r)
                model.AddBoolOr([room_assigned[(i, r)].Not(), room_assigned[(j, r)].Not()]).OnlyEnforceIf(both_same_r.Not())
                same_room_terms.append(both_same_r)

            same_room_sum = sum(same_room_terms)

            # Create helper variable: 1 if rooms differ, 0 if same
            diff_room = model.NewBoolVar(f"diff_room_{i}_{j}")
            model.Add(same_room_sum == 0).OnlyEnforceIf(diff_room)
            model.Add(same_room_sum == 1).OnlyEnforceIf(diff_room.Not())

            # Enforce 15-minute gap when same anesth and different rooms
            model.Add(start[j] >= end[i] + BUFFER).OnlyEnforceIf([
                anesth_assigned[(i, a)],
                anesth_assigned[(j, a)],
                diff_room,
            ])
    # --------------------------------------------
    # 3 Cost model per anesthesiologist
    # cost = max(5, shift_duration) + 0.5 * max(0, shift_duration - 9)
    # also enforce shift_duration <= 12 hours (720 min)
    # --------------------------------------------
    costs = []
    shift_durations = []  # to compute utilization later

    for a in range(max_anesth):
        start_a = model.NewIntVar(0, 24 * 60, f"start_a_{a}")
        end_a = model.NewIntVar(0, 24 * 60, f"end_a_{a}")

        # constrain start_a, end_a by surgeries assigned to this anesth
        for i in range(n):
            b = anesth_assigned[(i, a)]
            model.Add(start_a <= start[i]).OnlyEnforceIf(b)
            model.Add(end_a >= end[i]).OnlyEnforceIf(b)

        shift_duration = model.NewIntVar(0, MAX_SHIFT_MINUTES, f"dur_a_{a}")
        model.Add(shift_duration == end_a - start_a)

        # 12-hour max shift
        model.Add(shift_duration <= MAX_SHIFT_MINUTES)

        # base = max(5, shift_duration)
        base = model.NewIntVar(0, 24 * 60, f"base_a_{a}")
        model.AddMaxEquality(base, [shift_duration, model.NewConstant(5 * 60)])  # 5h=300min

        # extra = max(0, shift_duration - 9h)
        diff = model.NewIntVar(-24 * 60, 24 * 60, f"diff_a_{a}")
        model.Add(diff == shift_duration - 9 * 60)
        extra = model.NewIntVar(0, 24 * 60, f"extra_a_{a}")
        model.AddMaxEquality(extra, [diff, model.NewConstant(0)])

        # cost = base + 0.5 * extra (scale by 2)
        cost_scaled = model.NewIntVar(0, 10000, f"cost_scaled_a_{a}")
        model.Add(cost_scaled == 2 * base + extra).OnlyEnforceIf(an_used[a])
        model.Add(cost_scaled == 0).OnlyEnforceIf(an_used[a].Not())
        costs.append(cost_scaled)
        shift_durations.append(shift_duration)

    # Minimum utilization 80%
    total_surgery_minutes = int(df['dur_min'].sum())

    total_shift_terms = []
    for a in range(max_anesth):
        used_dur = model.NewIntVar(0, MAX_SHIFT_MINUTES, f"used_dur_{a}")
        model.Add(used_dur == shift_durations[a]).OnlyEnforceIf(an_used[a])
        model.Add(used_dur == 0).OnlyEnforceIf(an_used[a].Not())
        total_shift_terms.append(used_dur)

    total_shift_expr = sum(total_shift_terms)
    model.Add(100 * total_surgery_minutes >= 80 * total_shift_expr)


    model.Minimize(sum(costs))

    # --------------------------------------------
    # 4 Solve
    # --------------------------------------------
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = SOLVER_TIME_LIMIT
    solver.parameters.num_search_workers = 8

    status = solver.Solve(model)
    print("Solver status:", solver.StatusName(status))
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError("No feasible solution found")

    # --------------------------------------------
    # 5 Extract solution
    # --------------------------------------------
    sol = []
    for i in range(n):
        assigned_a = None
        assigned_r = None
        for a in range(max_anesth):
            if solver.Value(anesth_assigned[(i, a)]) == 1:
                assigned_a = a
                break
        for r in range(NUM_ROOMS):
            if solver.Value(room_assigned[(i, r)]) == 1:
                assigned_r = r
                break
        sol.append({
            'id': int(df.loc[i, 'id']),
            'start_min': int(df.loc[i, 'start_min']),
            'end_min': int(df.loc[i, 'end_min']),
            'anesth': assigned_a,
            'room': assigned_r,
        })

    # --------------------------------------------
    # Per-anesthesiologist stats
    # --------------------------------------------
    print("\nPer-Anesthesiologist Summary:")
    util_sum = 0
    util_count = 0

    for a in range(max_anesth):
        if solver.Value(an_used[a]) == 0:
            continue  # skip unused anesthesiologists

        shift_min = solver.Value(shift_durations[a])
        assigned_surgeries = [i for i in range(n) if solver.Value(anesth_assigned[(i, a)]) == 1]
        active_time_min = sum(df.loc[i, 'dur_min'] for i in assigned_surgeries)
        utilization_a = active_time_min / shift_min if shift_min > 0 else 0

        util_sum += utilization_a
        util_count += 1

        print(f"  Anesth {a:2d}: "
              f"Shift = {shift_min:4d} min, "
              f"Active = {active_time_min:4d} min, "
              f"Utilization = {utilization_a * 100:5.1f}%")

    # --------------------------------------------
    # Average utilization across used anesthesiologists
    # --------------------------------------------
    avg_utilization = (util_sum / util_count) if util_count > 0 else 0
    print(f"\nAverage individual utilization = {avg_utilization * 100:.1f}%")

    # difference appears whenever shift lengths differ.


    total_cost_scaled = sum(solver.Value(c) for c in costs)
    total_cost_hours = total_cost_scaled / 120.0  # divide by 2 and 60
    used_count = sum(1 for a in range(max_anesth) if solver.Value(an_used[a]) == 1)

    # Utilization ratio
    total_surgery_minutes = sum(df['dur_min'])
    total_shift_minutes = sum(
        solver.Value(shift_durations[a]) for a in range(max_anesth) if solver.Value(an_used[a]) == 1
    )
    utilization = total_surgery_minutes / total_shift_minutes if total_shift_minutes > 0 else 0

    # Rooms used
    rooms_used = sum(
        1 for r in range(NUM_ROOMS)
        if any(solver.Value(room_assigned[(i, r)]) == 1 for i in range(n))
    )

    print("\nSummary:")
    print(f"Total cost: {total_cost_hours:.2f}")
    print(f"Utilization: {utilization * 100:.1f}%")
    print(f"Total anesthesiologists used: {used_count}")
    print(f"Total rooms used: {rooms_used}")

    return sol, solver, total_cost_hours, utilization

def write_solution(sol, origin, filename="ortools_anesth_cost_solution.csv"):
    rows = []
    for item in sol:
        start_dt = origin + timedelta(minutes=item['start_min'])
        end_dt = origin + timedelta(minutes=item['end_min'])
        rows.append({
            'id': item['id'],
            'start_time': start_dt.strftime("%Y-%m-%d %H:%M"),
            'end_time': end_dt.strftime("%Y-%m-%d %H:%M"),
            'anesthetist_id': f"anesth-{item['anesth']}",
            'room_id': f"room-{item['room']}"
        })
    out_df = pd.DataFrame(rows)
    out_df.to_csv(filename, index=False)
    print(f"Wrote {len(rows)} rows to {filename}")
    return out_df


def main():
    start_time = time.time()

    df, origin = read_surgeries("surgeries.csv")
    print(f"Loaded {len(df)} surgeries. Origin = {origin}")

    sol, solver, total_cost, utilization = build_and_solve(df)
    out_df = write_solution(sol, origin)

    print(out_df.head())

    end_time = time.time()
    elapsed = end_time - start_time
    print(f"\nTotal runtime: {elapsed:.2f} seconds")

if __name__ == "__main__":
    main()
