# README

Used Linux OS to solve the assignment

## simple_greedy_solver.py 
### simple solver that acts as a benchmark base.
## To Run:
```
python simple_greedy_solver.py
```
## To Plot:
```
python plot_day_schedule.py ./simple_greedy_solution.csv
```
#### Results
Total cost: 246.50
Utilization: 55.3%
Total anesthesiologists used: 27
Total rooms used: 15
Total runtime: 0.11 seconds

## Overview:

It first assigns rooms first by taking any available rooms (from a minimum earliest time heap) by taking the rooms available that finished the earliest. This reduces the time required to search for an available room based on the heuristic that the earlier the surgery finishes within it, the more likely it is to be available. If no room is availble, assign it the earliest room to be free anyways and shift the time of the scheduled surgery by the time it takes for the room to be free.

It then assigns anesthesiologists (ATS) by iterating through ATS and assigning the first ATS that is available for the surgery while checking for 15 buffer time and full 12 hour shift. If no such ATS is available then a new ATS is created and assigned. We assume each ATS can only perform one shift of 12 hours in our entire allocation.

Runs very fast but not optimal

## ortools_solver.py 
### Complex solver that uses the OR-Tools library.
## To Run:
```
python ortools_anesth_cost_model_with_utilization.py
```
## To Plot:
```
python plot_day_schedule.py ./ortools_anesth_cost_solution.csv
```
#### Results

## When enforcing 82% utilization (more than that returns INFEASIBLE)
Total cost: 211.62
Utilization: 82.6%
Total anesthesiologists used: 24
Total rooms used: 15
Total runtime: 147.51 seconds


## When enforcing 80% utilization (more than that returns INFEASIBLE)
Total cost: 221.38
Utilization: 80.0%
Total anesthesiologists used: 43
Total rooms used: 20
Total runtime: 148.18 seconds


# OR-Tools Anesthesiologist Scheduling Model

This model schedules surgeries across anesthesiologists and operating rooms while minimizing total cost and maintaining high utilization.

---

## Model Overview

1. **Load Data:**  
   Reads a CSV of surgeries with `start` and `end` times, computes duration, and converts timestamps to minutes.

2. **Create Fixed Intervals:**  
   Each surgery has fixed start, end, and duration values used for time-based constraints.

3. **Assign Anesthesiologists:**  
   Each surgery is assigned to exactly one anesthesiologist; anesthesiologists cannot overlap in time (`NoOverlap`).

4. **Assign Rooms:**  
   Each surgery is assigned to exactly one of up to 20 rooms, also with `NoOverlap` constraints.

5. **Add 15-Minute Buffer:**  
   Enforces a 15-minute gap if an anesthesiologist switches to a different room between consecutive surgeries.

6. **Define Shift Durations:**  
   Each anesthesiologist’s shift spans from their first to last assigned surgery, capped at 12 hours.

7. **Compute Cost Function:**  
   Cost = `max(5h, shift)` + 0.5 × `max(0, shift − 9h)`; scaled for solver efficiency.

8. **Enforce Utilization ≥ 80%:**  
   Ensures total surgery minutes are at least 80% of total staffed anesthesiologist time.

9. **Solve & Output:**  
   Minimizes total cost, extracts assignments, prints utilization stats, and writes results to `ortools_anesth_cost_solution.csv`.

---


## Complexities Encountered
when building solution all at once it runs into infeasibility issues. Therefore it's always a good idea to built up model by adding variables/constraints one by one.

Adding 15 minute buffer is tricky:
At first tried just adding in 15 minute intervals after the solution is found and greedily push off any surgeries that extend beyond 12 hours to new anesthesiologists. Also tried assuming the worst and adding 15 minutes to each surgery. These didn't reach 80% utilization however so had to encode 15 minute buffer as variable/constraint.


## Future Directions:

To speed up solving assume that surgeries are only given in 15 minute intervals (as in example data) rather than any time and reduce search space.

Setting deterministic seed for reproducibility (currently difficult due to parallel workers)

Warm-Start - Starting from a greedy solution and optimizing?

Delaying surgery if no rooms available beyond 20. The given surgeries.csv data doesn't encounter this issue as 20 is more than enough

