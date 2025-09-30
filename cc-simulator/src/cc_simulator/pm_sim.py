from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

import simpy
from .scheme_config import (
    DEFAULT_SCHEME_CONFIG,
    QueueSystem,
    SchemeRuntimeMetrics,
)

SECONDS_IN_HOUR = 3600.0


@dataclass
class StageConfig:
    """Configuration for a single processing stage."""

    name: str
    service_mean: float  # seconds
    client_wait_mean: float  # seconds (mean time to wait for customer reply)
    sla_threshold: float  # seconds (queue + service target)

    def sample_service(self, rng: random.Random) -> float:
        if self.service_mean <= 0:
            return 0.0
        return rng.expovariate(1.0 / self.service_mean)

    def sample_client_wait(self, rng: random.Random) -> float:
        if self.client_wait_mean <= 0:
            return 0.0
        return rng.expovariate(1.0 / self.client_wait_mean)


@dataclass
class TeamConfig:
    name: str
    managers: int


@dataclass
class SimulationConfig:
    arrival_rate_per_hour: float
    horizon_hours: float = 8.0
    stages: List[StageConfig] = field(default_factory=list)
    teams: List[TeamConfig] = field(default_factory=list)
    sla_target_ratio: float = 0.8  # Probability to meet per-stage SLA

    def __post_init__(self) -> None:
        if not self.stages:
            raise ValueError("Simulation must define at least one stage")
        if not self.teams:
            raise ValueError("Simulation must define at least one team")
        if self.arrival_rate_per_hour <= 0:
            raise ValueError("Arrival rate must be positive")
        if self.horizon_hours <= 0:
            raise ValueError("Horizon must be positive")


@dataclass
class StageStats:
    processed: int = 0
    queue_wait_total: float = 0.0
    service_total: float = 0.0
    client_wait_total: float = 0.0
    sla_hits: int = 0

    def as_dict(self, stage: StageConfig) -> Dict[str, float]:
        if self.processed:
            avg_queue = self.queue_wait_total / self.processed
            avg_service = self.service_total / self.processed
            avg_client = self.client_wait_total / self.processed
            sla_ratio = self.sla_hits / self.processed
        else:
            avg_queue = avg_service = avg_client = sla_ratio = 0.0
        return {
            "processed": self.processed,
            "avgQueueWait": avg_queue,
            "avgService": avg_service,
            "avgClientWait": avg_client,
            "slaThreshold": stage.sla_threshold,
            "slaHitRatio": sla_ratio,
        }


@dataclass
class TeamStats:
    name: str
    managers: int
    busy_time_total: float = 0.0
    processed_jobs: int = 0

    def as_dict(self, horizon_seconds: float) -> Dict[str, float]:
        utilization = (
            self.busy_time_total / (self.managers * horizon_seconds)
            if horizon_seconds > 0 and self.managers > 0
            else 0.0
        )
        return {
            "name": self.name,
            "managers": self.managers,
            "processed": self.processed_jobs,
            "utilization": utilization,
        }


@dataclass
class Job:
    job_id: int
    team_idx: int  # initial team assignment (entry team)
    created_at: float
    stage_index: int = 0
    queue_enter_at: float = 0.0
    last_service_start: float = 0.0
    manager_idx: Optional[int] = None
    route_history: List[Tuple[float, int, int]] = field(default_factory=list)  # (time, fromTeam, toTeam)


class MetricsCollector:
    """Collect per-stage statistics and time series."""

    def __init__(self, config: SimulationConfig) -> None:
        self.config = config
        stage_count = len(config.stages)
        self.stage_stats: List[StageStats] = [StageStats() for _ in range(stage_count)]
        self.team_stats: List[TeamStats] = [
            TeamStats(name=team.name, managers=team.managers)
            for team in config.teams
        ]
        self.total_arrivals = 0
        self.total_completed = 0
        self.current_queue: List[int] = [0] * stage_count
        self.current_in_service: List[int] = [0] * stage_count
        self.current_waiting_client: List[int] = [0] * stage_count
        self.minute_log = {
            "t": [],
            "queue": [[] for _ in range(stage_count)],
            "inService": [[] for _ in range(stage_count)],
            "waitingClient": [[] for _ in range(stage_count)],
        }

    # --- queue level bookkeeping -------------------------------------------------
    def queue_enter(self, stage_idx: int) -> None:
        self.current_queue[stage_idx] += 1

    def queue_leave(self, stage_idx: int) -> None:
        self.current_queue[stage_idx] -= 1

    def service_start(
        self,
        stage_idx: int,
        team_idx: int,
        manager_idx: int,
        queue_wait: float,
    ) -> None:
        self.current_in_service[stage_idx] += 1
        stats = self.stage_stats[stage_idx]
        stats.queue_wait_total += queue_wait

    def service_end(self, stage_idx: int, service_time: float) -> None:
        self.current_in_service[stage_idx] -= 1
        self.stage_stats[stage_idx].service_total += service_time

    def client_wait_start(self, stage_idx: int) -> None:
        self.current_waiting_client[stage_idx] += 1

    def client_wait_end(self, stage_idx: int, wait_time: float) -> None:
        self.current_waiting_client[stage_idx] -= 1
        self.stage_stats[stage_idx].client_wait_total += wait_time

    def sla_check(self, stage_idx: int, queue_wait: float, service_time: float) -> None:
        stats = self.stage_stats[stage_idx]
        stats.processed += 1
        threshold = self.config.stages[stage_idx].sla_threshold
        if (queue_wait + service_time) <= threshold:
            stats.sla_hits += 1

    def register_busy(self, team_idx: int, busy_time: float) -> None:
        self.team_stats[team_idx].busy_time_total += busy_time

    def add_arrival(self) -> None:
        self.total_arrivals += 1

    def add_completion(self, team_idx: int) -> None:
        self.total_completed += 1
        self.team_stats[team_idx].processed_jobs += 1

    def snapshot(self, env_now: float) -> None:
        self.minute_log["t"].append(env_now)
        for idx in range(len(self.current_queue)):
            self.minute_log["queue"][idx].append(self.current_queue[idx])
            self.minute_log["inService"][idx].append(self.current_in_service[idx])
            self.minute_log["waitingClient"][idx].append(self.current_waiting_client[idx])

    # --- result serialization ----------------------------------------------------
    def build_results(self, horizon_seconds: float) -> Dict[str, object]:
        stage_payload = [
            stats.as_dict(stage)
            for stats, stage in zip(self.stage_stats, self.config.stages)
        ]
        team_payload = [ts.as_dict(horizon_seconds) for ts in self.team_stats]
        unfinished = self.total_arrivals - self.total_completed
        return {
            "summary": {
                "totalArrivals": self.total_arrivals,
                "completed": self.total_completed,
                "unfinished": unfinished,
                "horizonSeconds": horizon_seconds,
            },
            "stages": stage_payload,
            "teams": team_payload,
            "timeline": self.minute_log,
        }


class Manager:
    def __init__(
        self,
        env: simpy.Environment,
        team_idx: int,
        manager_idx: int,
        config: SimulationConfig,
        metrics: MetricsCollector,
        rng: random.Random,
        scheme_cfg: dict,
        queue_system: QueueSystem,
        runtime_metrics: SchemeRuntimeMetrics,
    ) -> None:
        self.env = env
        self.team_idx = team_idx
        self.manager_idx = manager_idx
        self.config = config
        self.metrics = metrics
        self.rng = rng
        self.scheme_cfg = scheme_cfg
        self.queue_system = queue_system
        self.runtime_metrics = runtime_metrics
        self.queue: simpy.Store[Job] = simpy.Store(env)
        self.busy_time = 0.0
        self.process = env.process(self._run())

    def enqueue(self, job: Job) -> None:
        job.queue_enter_at = self.env.now
        job.manager_idx = self.manager_idx
        self.metrics.queue_enter(job.stage_index)
        self.queue.put(job)

    def _maybe_manager_feedback(self, job: Job) -> None:
        prob = self.scheme_cfg["feedback"]["manager_feedback"]
        if self.rng.random() < prob:
            # Create feedback task (lightweight placeholder referencing original job id)
            fb_task = {"refJob": job.job_id, "createdAt": self.env.now}
            self.queue_system.add_manager_feedback(fb_task)
            self.runtime_metrics.feedback_tasks_generated += 1

    def _run(self) -> Iterable[float]:
        while True:
            job = yield self.queue.get()
            stage_idx = job.stage_index
            stage_cfg = self.config.stages[stage_idx]

            queue_wait = self.env.now - job.queue_enter_at
            self.metrics.queue_leave(stage_idx)
            self.metrics.service_start(stage_idx, job.team_idx, self.manager_idx, queue_wait)

            # Adjust service time by team efficiency if provided
            eff_map = self.scheme_cfg["teams"]["efficiencies"]
            base_service = stage_cfg.sample_service(self.rng)
            eff = eff_map.get(self.team_idx + 1, 1.0)
            service_time = base_service / max(0.01, eff)
            if service_time < 0:
                service_time = 0.0

            self.busy_time += service_time
            yield self.env.timeout(service_time)

            self.metrics.service_end(stage_idx, service_time)
            self.metrics.register_busy(job.team_idx, service_time)
            self.metrics.sla_check(stage_idx, queue_wait, service_time)

            # Manager feedback possibility
            self._maybe_manager_feedback(job)

            # Transition logic with probabilities
            if stage_idx >= len(self.config.stages) - 1:
                self.metrics.add_completion(job.team_idx)
                continue

            probs = self.scheme_cfg["probabilities"]
            next_roll = self.rng.random()
            advance = False
            if stage_idx == 0:  # FL -> PI chance
                if next_roll < probs["fl_to_pi"]:
                    advance = True
            elif stage_idx == 1:  # PI -> KOD chance
                if next_roll < probs["pi_to_cod"]:
                    advance = True
            # completion chance otherwise
            complete_chance = probs["completion_rate"]
            if not advance and self.rng.random() < complete_chance:
                self.metrics.add_completion(job.team_idx)
                continue

            # If advancing stage
            if advance:
                wait_time = stage_cfg.sample_client_wait(self.rng)
                if wait_time < 0:
                    wait_time = 0.0
                if wait_time > 0:
                    self.metrics.client_wait_start(stage_idx)
                    self.env.process(self._resume_after_wait(job, wait_time, stage_idx))
                else:
                    job.stage_index += 1
                    self.enqueue(job)
            else:
                # treat as complete if not advanced and not completed by probability (fallback)
                self.metrics.add_completion(job.team_idx)

    def _resume_after_wait(self, job: Job, wait_time: float, stage_idx: int) -> Iterable[float]:
        yield self.env.timeout(wait_time)
        self.metrics.client_wait_end(stage_idx, wait_time)
        job.stage_index += 1
        self.enqueue(job)


class Team:
    def __init__(
        self,
        env: simpy.Environment,
        team_idx: int,
        config: SimulationConfig,
        metrics: MetricsCollector,
        rng: random.Random,
        scheme_cfg: dict,
        queue_system: QueueSystem,
        rt_metrics: SchemeRuntimeMetrics,
    ) -> None:
        self.env = env
        self.team_idx = team_idx
        self.config = config
        self.metrics = metrics
        self.rng = rng
        self.scheme_cfg = scheme_cfg
        self.queue_system = queue_system
        self.rt_metrics = rt_metrics
        self.managers: List[Manager] = [
            Manager(env, team_idx, idx, config, metrics, rng, scheme_cfg, queue_system, rt_metrics)
            for idx in range(config.teams[team_idx].managers)
        ]
        if not self.managers:
            raise ValueError("Team must have at least one manager")

    def assign(self, job: Job) -> None:
        manager = min(self.managers, key=lambda m: len(m.queue.items))
        manager.enqueue(job)


class ProgramManagerSimulation:
    def __init__(self, config: SimulationConfig, seed: Optional[int] = None, scheme_config: Optional[dict] = None) -> None:
        self.config = config
        self.seed = seed
        self.rng = random.Random(seed)
        self.env = simpy.Environment()
        self.metrics = MetricsCollector(config)
        self.scheme_cfg = scheme_config or DEFAULT_SCHEME_CONFIG
        self.runtime_metrics = SchemeRuntimeMetrics()
        team_ids = list(range(1, len(config.teams) + 1))
        self.queue_system = QueueSystem(team_ids)
        self.teams = [
            Team(
                self.env,
                idx,
                config,
                self.metrics,
                random.Random(self.rng.randint(0, 1_000_000)),
                self.scheme_cfg,
                self.queue_system,
                self.runtime_metrics,
            )
            for idx in range(len(config.teams))
        ]
        self.horizon_seconds = config.horizon_hours * SECONDS_IN_HOUR
        self.job_counter = 0
        self._rr_pointer = 0  # for potential round-robin
        self.env.process(self._arrival_process())
        self.env.process(self._minute_sampler())
        self.env.process(self._redistribution_loop())

    # ------------------------------------------------------------------ processes
    def _arrival_process(self) -> Iterable[float]:
        lambda_per_sec = self.config.arrival_rate_per_hour / SECONDS_IN_HOUR
        if lambda_per_sec <= 0:
            return
        policy = self.scheme_cfg["routing"]["policy"]
        while True:
            interarrival = self.rng.expovariate(lambda_per_sec)
            yield self.env.timeout(interarrival)
            if self.env.now > self.horizon_seconds:
                break
            job = Job(job_id=self.job_counter, team_idx=0, created_at=self.env.now)
            self.job_counter += 1
            self.metrics.add_arrival()
            # Dynamic routing among teams using queue lengths (sum of manager queues)
            current_loads = {
                tid + 1: sum(len(m.queue.items) for m in team.managers)
                for tid, team in enumerate(self.teams)
            }
            assigned_team_id, where = self.queue_system.dynamic_routing(job, current_loads, policy=policy)
            # 'where' can be main or idle fallback; if main we dispatch immediately
            if where == "main":
                team_obj = self.teams[assigned_team_id - 1]
                team_obj.assign(job)
            # if idle fallback — it sits until redistribution

    def _minute_sampler(self) -> Iterable[float]:
        while True:
            yield self.env.timeout(60.0)
            if self.env.now > self.horizon_seconds:
                break
            self.metrics.snapshot(self.env.now)
            # consume one feedback task opportunistically
            if self.queue_system.feedback_queue:
                fb_task = self.queue_system.feedback_queue.pop(0)
                self.runtime_metrics.feedback_tasks_consumed += 1
                # Feedback becomes a new Job entering at stage 0
                job = Job(job_id=self.job_counter, team_idx=0, created_at=self.env.now)
                self.job_counter += 1
                self.metrics.add_arrival()
                current_loads = {
                    tid + 1: sum(len(m.queue.items) for m in team.managers)
                    for tid, team in enumerate(self.teams)
                }
                assigned_team_id, where = self.queue_system.dynamic_routing(
                    job, current_loads, policy=self.scheme_cfg["routing"]["policy"]
                )
                if where == "main":
                    self.teams[assigned_team_id - 1].assign(job)

    def _redistribution_loop(self) -> Iterable[float]:
        interval = self.scheme_cfg["routing"].get("redistribution_interval", 300)
        rate_gate = self.scheme_cfg["feedback"].get("idle_redistribution_rate", 0.15)
        while True:
            yield self.env.timeout(interval)
            if self.env.now > self.horizon_seconds:
                break
            if self.rng.random() <= rate_gate:
                current_loads = {
                    tid + 1: sum(len(m.queue.items) for m in team.managers)
                    for tid, team in enumerate(self.teams)
                }
                moved = self.queue_system.redistribute_idle_tasks(current_loads)
                if moved:
                    self.runtime_metrics.redistribution_events += moved
                # Any tasks moved to main_queues should be immediately dispatched
                for tid, q in list(self.queue_system.main_queues.items()):
                    while q:
                        job = q.pop(0)
                        self.teams[tid - 1].assign(job)

    # --------------------------------------------------------------------- public
    def run(self) -> Dict[str, object]:
        self.env.run(until=self.horizon_seconds)
        self.metrics.snapshot(self.horizon_seconds)
        result = self.metrics.build_results(self.horizon_seconds)
        # Append detailed queue & scheme metrics
        result["scheme"] = {
            "queues": self.queue_system.snapshot_lengths(),
            "runtime": self.runtime_metrics.as_dict(),
            "routingPolicy": self.scheme_cfg["routing"]["policy"],
            "probabilities": self.scheme_cfg["probabilities"],
            "feedback": self.scheme_cfg.get("feedback", {}),
        }
        return result


def default_simulation_config(arrival_rate: float = 250.0) -> SimulationConfig:
    stages = [
        StageConfig("FIO", service_mean=120.0, client_wait_mean=120.0, sla_threshold=120.0),
        StageConfig("FL", service_mean=1356.0, client_wait_mean=1356.0, sla_threshold=1356.0),
        StageConfig("PI", service_mean=4398.0, client_wait_mean=4398.0, sla_threshold=4398.0),
        StageConfig("KOD", service_mean=7332.0, client_wait_mean=7332.0, sla_threshold=7332.0),
    ]
    teams = [TeamConfig(f"PM {i+1}", managers=10) for i in range(5)]
    return SimulationConfig(
        arrival_rate_per_hour=arrival_rate,
        stages=stages,
        teams=teams,
    )


def optimize_staff(
    config: SimulationConfig,
    min_managers: int = 1,
    max_managers: int = 40,
    seed: Optional[int] = None,
    scheme_config: Optional[dict] = None,
) -> Dict[str, object]:
    """Brute-force search for minimal staffing meeting SLA targets (scheme-aware)."""

    best_result: Optional[Dict[str, object]] = None
    best_count: Optional[int] = None
    lambda_per_hour = config.arrival_rate_per_hour

    for managers in range(min_managers, max_managers + 1):
        for team_cfg in config.teams:
            team_cfg.managers = managers
        sim = ProgramManagerSimulation(config, seed=seed, scheme_config=scheme_config)
        result = sim.run()
        sla_ok = all(
            stage["slaHitRatio"] >= config.sla_target_ratio for stage in result["stages"]
        )
        if sla_ok:
            min_stage_sla = min((s["slaHitRatio"] for s in result["stages"]), default=0.0)
            total_managers = sum(t["managers"] for t in result["teams"])
            result["staffing"] = {
                "directors": 0,
                "stageManagers": total_managers,
                "perTeam": {t["name"]: t["managers"] for t in result["teams"]},
            }
            result["metrics"] = {
                "minStageSLA": min_stage_sla,
                "targetSLA": config.sla_target_ratio,
                "teams": len(result["teams"]),
            }
            best_result = result
            best_count = managers
            break

    if best_result is None:
        return {
            "found": False,
            "managers": None,
            "result": None,
            "arrivalRate": lambda_per_hour,
        }

    return {
        "found": True,
        "managers": best_count,
        "result": best_result,
        "arrivalRate": lambda_per_hour,
    }
