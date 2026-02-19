"""Dependency-aware multi-wave planner with DAG validation and LPT bin packing."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

import networkx as nx  # type: ignore[import-untyped]

from agent_estimate.core.models import (
    AgentProfile,
    TaskNode,
    Wave,
    WaveAssignment,
    WavePlan,
)


def plan_waves(
    tasks: Sequence[TaskNode],
    agents: Sequence[AgentProfile],
    inter_wave_overhead_hours: float = 0.25,
) -> WavePlan:
    """Schedule tasks into dependency-respecting waves using LPT bin packing.

    Args:
        tasks: Task nodes with durations and dependency edges.
        agents: Agent profiles; each agent contributes ``parallelism`` slots.
        inter_wave_overhead_hours: Idle time inserted between consecutive waves.

    Returns:
        A ``WavePlan`` with waves, critical path, and utilisation metrics.

    Raises:
        ValueError: If the dependency graph contains a cycle, a task requires
            capabilities that no agent provides, a dependency references an
            unknown task, or no agents are provided.
    """
    if inter_wave_overhead_hours < 0:
        raise ValueError(
            f"inter_wave_overhead_hours must be >= 0, got {inter_wave_overhead_hours}"
        )

    if not tasks:
        return WavePlan(
            waves=(),
            critical_path=(),
            critical_path_minutes=0.0,
            agent_utilization={},
            parallel_efficiency=0.0,
            total_wall_clock_minutes=0.0,
            total_sequential_minutes=0.0,
        )

    # ------------------------------------------------------------------
    # 1. Build DAG
    # ------------------------------------------------------------------
    G = nx.DiGraph()
    task_map: dict[str, TaskNode] = {}
    for t in tasks:
        task_map[t.task_id] = t
        G.add_node(t.task_id, duration_minutes=t.duration_minutes)
    for t in tasks:
        for dep in t.dependencies:
            if dep not in task_map:
                raise ValueError(
                    f"Task {t.task_id!r} depends on unknown task {dep!r}"
                )
            G.add_edge(dep, t.task_id)

    # ------------------------------------------------------------------
    # 2. Validate — acyclic
    # ------------------------------------------------------------------
    if not nx.is_directed_acyclic_graph(G):
        cycle = nx.find_cycle(G, orientation="original")
        cycle_path = [u for u, _v, _dir in cycle] + [cycle[0][0]]
        raise ValueError(f"Dependency cycle detected: {' -> '.join(cycle_path)}")

    # ------------------------------------------------------------------
    # 3. Expand agent slots
    # ------------------------------------------------------------------
    if not agents:
        raise ValueError("At least one agent is required to schedule tasks.")

    # Each slot is (agent_name, slot_index) with a set of capabilities.
    slots: list[tuple[str, int, set[str]]] = []
    for agent in agents:
        caps = set(agent.capabilities)
        for i in range(agent.parallelism):
            slots.append((agent.name, i, caps))

    # ------------------------------------------------------------------
    # 4. Levelisation via topological generations
    # ------------------------------------------------------------------
    generations = list(nx.topological_generations(G))

    # ------------------------------------------------------------------
    # 5. LPT bin packing per level → waves
    # ------------------------------------------------------------------
    overhead_minutes = inter_wave_overhead_hours * 60
    waves: list[Wave] = []
    current_time = 0.0
    # Track cumulative load per slot across all waves (for utilisation later)
    slot_load: dict[tuple[str, int], float] = defaultdict(float)

    for gen_index, generation in enumerate(generations):
        # Sort tasks longest-first (LPT)
        sorted_tasks = sorted(generation, key=lambda tid: task_map[tid].duration_minutes, reverse=True)

        # Per-wave bin loads (reset each wave)
        wave_bin_load: dict[tuple[str, int], float] = defaultdict(float)
        assignments: list[WaveAssignment] = []

        for tid in sorted_tasks:
            node = task_map[tid]
            required = set(node.required_capabilities)

            # Find eligible slots
            eligible = [
                (name, idx)
                for name, idx, caps in slots
                if required.issubset(caps)
            ]
            if not eligible:
                raise ValueError(
                    f"No eligible agent for task {tid!r} "
                    f"(requires {sorted(required)})"
                )

            # Pick the eligible slot with minimum current wave load
            best = min(eligible, key=lambda s: wave_bin_load[s])
            wave_bin_load[best] += node.duration_minutes
            slot_load[best] += node.duration_minutes

            assignments.append(
                WaveAssignment(
                    task_id=tid,
                    agent_name=best[0],
                    slot_index=best[1],
                    duration_minutes=node.duration_minutes,
                )
            )

        # Wave makespan = max bin load in this wave
        wave_makespan = max(wave_bin_load.values()) if wave_bin_load else 0.0
        wave_start = current_time
        wave_end = wave_start + wave_makespan

        waves.append(
            Wave(
                wave_number=gen_index,
                start_minutes=wave_start,
                end_minutes=wave_end,
                assignments=tuple(assignments),
            )
        )

        # Advance time (add overhead unless this is the last wave)
        current_time = wave_end
        if gen_index < len(generations) - 1:
            current_time += overhead_minutes

    # ------------------------------------------------------------------
    # 6. Critical path (node-weighted)
    # ------------------------------------------------------------------
    # nx.dag_longest_path uses edge weights; we need node weights.
    # DP over topological order: dist[v] = duration[v] + max(dist[u] for u in preds).
    topo_order = list(nx.topological_sort(G))
    dist: dict[str, float] = {}
    prev: dict[str, str | None] = {}
    for v in topo_order:
        predecessors = list(G.predecessors(v))
        if not predecessors:
            dist[v] = G.nodes[v]["duration_minutes"]
            prev[v] = None
        else:
            best_pred = max(predecessors, key=lambda u: dist[u])
            dist[v] = dist[best_pred] + G.nodes[v]["duration_minutes"]
            prev[v] = best_pred

    # Reconstruct path from the node with maximum distance
    end_node = max(topo_order, key=lambda v: dist[v])
    critical_path_minutes = dist[end_node]
    path: list[str] = []
    node: str | None = end_node
    while node is not None:
        path.append(node)
        node = prev[node]
    path.reverse()
    critical_path = tuple(path)

    # ------------------------------------------------------------------
    # 7. Metrics
    # ------------------------------------------------------------------
    total_wall_clock = waves[-1].end_minutes if waves else 0.0
    total_sequential = sum(t.duration_minutes for t in tasks)

    # Per-agent utilisation: busy_time / wall_clock
    # Initialise all input agents to 0.0 so idle agents appear in the output.
    agent_busy: dict[str, float] = {agent.name: 0.0 for agent in agents}
    for (name, _idx), load in slot_load.items():
        agent_busy[name] += load

    if total_wall_clock > 0:
        agent_utilization = {
            name: busy / total_wall_clock for name, busy in sorted(agent_busy.items())
        }
        parallel_efficiency = min(1.0, total_sequential / (len(slots) * total_wall_clock))
    else:
        agent_utilization = {agent.name: 0.0 for agent in agents}
        parallel_efficiency = 0.0

    return WavePlan(
        waves=tuple(waves),
        critical_path=critical_path,
        critical_path_minutes=critical_path_minutes,
        agent_utilization=agent_utilization,
        parallel_efficiency=parallel_efficiency,
        total_wall_clock_minutes=total_wall_clock,
        total_sequential_minutes=total_sequential,
    )
