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

## When enforcing 82% utilization (maximum achieved)
Total cost: 211.62

Utilization: 82.6%

Total anesthesiologists used: 24

Total rooms used: 15

Total runtime: 147.51 seconds


## When enforcing 80% utilization
Total cost: 221.38

Utilization: 80.0%

Total anesthesiologists used: 43

Total rooms used: 20

Total runtime: 148.18 seconds


## OR-Tools Anesthesiologist Scheduling Model

This model schedules surgeries across anesthesiologists and operating rooms while minimizing total cost and maintaining high utilization.

---

### Model Overview

1. **Load Data:**  
   Reads a CSV of surgeries with `start` and `end` times, computes duration, and converts timestamps to minutes.

2. **Create Fixed Intervals:**  
   Each surgery has fixed start, end, and duration values used for time-based constraints. These aren’t decision variables (the times are fixed) but they’re modeled as fixed IntVars for compatibility with interval variables later.

3. **Assign Anesthesiologists:**  
   Each surgery is assigned to exactly one anesthesiologist; anesthesiologists cannot overlap in time (`NoOverlap`). Track which anesthesiologists are used for use later in cost calculation and for symmetry-breaking constraint so that earlier IDs can’t be unused if later ones are used, reducing search space.

4. **Assign Rooms:**  
   Each surgery is assigned to exactly one of up to 20 rooms, also with `NoOverlap` constraints so that no two surgeries can be in the same room.

5. **Add 15-Minute Buffer:**  
   Enforces a 15-minute gap if an anesthesiologist switches to a different room between consecutive surgeries.
   1) Finds all consecutive surgeries
   2) Defines same room boolean SR for consectuive surgery i,j in ssame room r
   3) Enforces SR(i,j,r) <-> Room_Assigned(i,r) ^ Room_Assigned(j, r) This creates NUM_ROOMS Boolean indicators (for each consecutive surgery for each ANT)
   4) Defines same_room_sum = Sum(same_room_terms) same_room_sum is 1 if any of the rooms for a pair of consecutive surgeries for a particular ANT are the same room (enforced by Room_Assigned condition), 0 otherwise. We don't worry about sum > 1 because this done for each consecutive pair of surgeries and there can only be one instance of these surgeries either in exactly one room or 2 separate rooms (enforced previously with ExactlyOne constraint beforehand).
   5) Use helper function to add 15 min buffer constraint to surgery end for any ANT that is assigned 2 consecutive surgeries in different room

6. **Define Shift Durations:**  
   Each anesthesiologist’s shift spans from their first to last assigned surgery, capped at 12 hours.

7. **Compute Cost Function:**  
   Cost = `max(5h, shift)` + 0.5 × `max(0, shift − 9h)`; scaled for solver efficiency.

8. **Enforce Utilization ≥ 80%:**  
   Ensures total surgery minutes are at least 80% of total staffed anesthesiologist time.

9. **Solve & Output:**  
   Minimizes total cost, extracts assignments, prints utilization stats, and writes results to `ortools_anesth_cost_solution.csv`.

---
### Problem Complexity:
$(n \times R)^{n}$

where:  
$n$ = number of *surgeries* to schedule,
$R$ = number of *rooms* available,
$n \times R$ = number of possible *(anesthesiologist, room)* combinations for a single surgery,
and $(n \times R)^{n}$ represents all possible independent assignments of anesthesiologist–room pairs across all $n$ surgeries.

### Variables/Constraints used:
% Variables
$start_i, end_i$ : integer surgery start/end (fixed from data).
$d_i$ : surgery duration (constant).
$an_{i,a}\in\{0,1\}$ : Bool, surgery $i$ assigned to anesthesiologist $a$.
$I_{i,a}$ : optional interval for surgery $i$ on anesth $a$ (exists iff $an_{i,a}=1$).
$an\_used_a\in\{0,1\}$ : Bool, anesthesiologist $a$ is used.
$room_{i,r}\in\{0,1\}$ : Bool, surgery $i$ assigned to room $r$.
$J_{i,r}$ : optional interval for surgery $i$ in room $r$.
$both\_same_{i,j,r}\in\{0,1\}$ : Bool, $i$ and $j$ both in room $r$.
$diff\_room_{i,j}\in\{0,1\}$ : Bool, $i,j$ are in different rooms.
$start\_a, end\_a$ : integer shift start/end for anesth $a$.
$shift_a$ : integer shift duration for anesth $a$.
$base_a, diff_a, extra_a$ : auxiliary integers for piecewise cost.
$cost\_scaled_a$ : integer scaled cost for anesth $a$.
$used\_dur_a$ : integer = $shift_a$ if anesth used else $0$.

% Constraints
1) Timing: $e_i = s_i + d_i$ (surgery times fixed).  
2) Exactly-one: $\sum_a an_{i,a} = 1$ and $\sum_r room_{i,r} = 1$ for each surgery $i$.  
3) No-overlap: $AddNoOverlap(\{I_{i,a}\}_i)$ per anesth $a$, and $AddNoOverlap(\{J_{i,r}\}_i)$ per room $r$.  
4) Anesth-used: $an\_used_a = \max_i an_{i,a}$.  
5) Symmetry breaking: $an\_used_{a-1} \ge an\_used_a$.  
6) Buffer: for consecutive $(i,j)$ with $end_i = start_j$, enforce $start_j \ge end_i + 15$ only if $an_{i,a}=1$, $an_{j,a}=1$, and $diff\_room_{i,j}=1$.  
7) Room-difference logic: $both\_same_{i,j,r} \leftrightarrow (room_{i,r} \wedge room_{j,r})$, $same\_room\_sum = \sum_r both\_same_{i,j,r} \in\{0,1\}$, $diff\_room_{i,j}=1 \Leftrightarrow same\_room\_sum=0$.  
8) Shift linking: If $an_{i,a}=1$ then $start\_a \le start_i$ and $end\_a \ge end_i$. $shift_a = end_a - start_a$, $shift_a \le$ MAX_SHIFT.  
9) Cost piecewise: $base_a = \max(shift_a,5\text{h})$, $diff_a = shift_a - 9\text{h}$, $extra_a=\max(diff_a,0)$, $cost\_scaled_a = 2\cdot base_a + extra_a$ if $an\_used_a=1$ else $0$.  
10) Utilization: Let $S=\sum_i d_i$ and $T=\sum_a used\_dur_a$. Enforce $100\cdot S \ge 80\cdot T$ (i.e. $S/T \ge 0.8$).

% Objective
Minimize $\sum_a cost\_scaled_a$ (final reported cost = $\frac{1}{120}\sum_a cost\_scaled_a$).

## Complexities Encountered
When building solution all at once it runs into infeasibility issues. Therefore it's always a good idea to built up model by adding variables/constraints one by one.

Adding 15 minute buffer is tricky:
At first tried just adding in 15 minute intervals after the solution is found and greedily push off any surgeries that extend beyond 12 hours to new anesthesiologists. Also tried assuming the worst and adding 15 minutes to each surgery. These didn't reach 80% utilization however so had to encode 15 minute buffer as variable/constraint.


## Future Directions:

Even 82% utilization has some obvious improvements in schedule somtimes from just looking at it.

To speed up solving assume that surgeries are only given in 15 minute intervals (as in example data) rather than any time and reduce search space.

Setting deterministic seed for reproducibility (currently difficult due to parallel workers)

Warm-Start - Starting from a greedy solution and optimizing?

Delaying surgery if no rooms available beyond 20. The given surgeries.csv data doesn't encounter this issue as 20 is more than enough
<img width="1848" height="974" alt="Schedule_Solution_80%_utilization" src="https://github.com/user-attachments/assets/2157e84e-7c50-4a65-8654-53f29c30dc3c" />

