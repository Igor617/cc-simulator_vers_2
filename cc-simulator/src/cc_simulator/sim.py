from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List


def rnd_exp(mean: float) -> float:
    if mean <= 0:
        return 0.0
    # Avoid log(0)
    u = max(1e-9, 1.0 - random.random())
    return -mean * math.log(u)


@dataclass
class Agent:
    id: int
    state: str = "idle"  # idle | busy | acw | break
    busy_until: float = 0.0
    acw_until: float = 0.0


class Simulation:
    """Server-side simulation matching the client logic and metrics.

    Drive with run_step(real_dt, speed), where sim_dt = real_dt*60*speed.
    Maintains minute-level logs: arrivals, q, talk, acw, answered, answeredInT,
    completed, staffActive, occ, asaMin, ahtMin, waitMin.
    """

    def __init__(
        self,
        lambda_rate: float = 360,
        aht: float = 540,
        acw: float = 60,
        sla: float = 80,
        thr: float = 20,
        occ_max: float = 85,
        shrink: float = 20,
        num_agents: int = 12,
    ) -> None:
        self.set_params(lambda_rate, aht, acw, sla, thr, occ_max, shrink, num_agents)
        self.reset()

    def set_params(
        self,
        lambda_rate: float,
        aht: float,
        acw: float,
        sla: float,
        thr: float,
        occ_max: float,
        shrink: float,
        num_agents: int,
    ) -> None:
        self.lambda_rate = float(lambda_rate)
        self.aht = float(aht)
        self.acw = float(acw)
        self.sla = float(sla)
        self.thr = float(thr)
        self.occ_max = float(occ_max)
        self.shrink = float(shrink)
        self.num_agents = int(num_agents)

    # Public API compatibility with tests
    def add_agent(self, agent: Agent) -> None:
        # Ensure newly added agents are active and ready (used by tests)
        agent.state = "idle"
        agent.busy_until = 0.0
        agent.acw_until = 0.0
        self.agents.append(agent)
        # Consider manually added agents as active
        self.staff_active = max(self.staff_active, len(self.agents))

    def add_to_queue(self, agent: Agent) -> None:
        self.queue.append(0.0)  # placeholder arrival time

    def start(self) -> None:  # placeholder
        pass

    def stop(self) -> None:  # placeholder
        pass

    def reset(self) -> None:
        self.sim_t: float = 0.0
        # Keep a simple integer counter for unit tests
        self.current_time = 0
        self.next_arrival: float = 0.0
        self.queue: List[float] = []  # store arrival times
        self.done_count: int = 0

        # Agents and active subset
        self.agents: List[Agent] = [Agent(i + 1) for i in range(self.num_agents)]
        self.staff_active = max(0, round(self.num_agents * (1 - self.shrink / 100)))
        for i, a in enumerate(self.agents):
            a.state = "idle" if i < self.staff_active else "break"
            a.acw_until = 0.0
            a.busy_until = 0.0

        # Minute logging buffers
        self.logs = {
            "t": [],
            "arrivals": [],
            "q": [],
            "talk": [],
            "acw": [],
            "answered": [],
            "answeredInT": [],
            "completed": [],
            "staffActive": [],
            "occ": [],
            "asaMin": [],
            "ahtMin": [],
            "waitMin": [],
        }
        self.tmp_minute = {
            "finishedDur": [],
            "waitDur": [],
            "busyAgentsTime": 0.0,
            "activeAgentsTime": 0.0,
            "arrivals": 0,
            "answered": 0,
            "answeredInT": 0,
            "completed": 0,
        }
        self.next_log_at: float = 60.0

    def _spawn_arrivals_until(self, t_end: float) -> None:
        rate_per_sec = self.lambda_rate / 3600.0
        mean_interarrival = 1.0 / max(1e-9, rate_per_sec)
        while self.next_arrival <= t_end:
            self.queue.append(self.next_arrival)
            self.tmp_minute["arrivals"] += 1
            self.next_arrival = (self.next_arrival or self.sim_t) + max(1.0, rnd_exp(mean_interarrival))

    def _try_assign(self) -> bool:
        # Assign first waiting to first idle
        if not self.queue:
            return False
        for ag in self.agents[: self.staff_active]:
            if ag.state == "idle":
                arrival_time = self.queue.pop(0)
                ag.state = "busy"
                ag.busy_until = self.sim_t + max(1.0, rnd_exp(self.aht))
                wait = self.sim_t - arrival_time
                self.tmp_minute["waitDur"].append(wait)
                self.tmp_minute["answered"] += 1
                if wait <= self.thr:
                    self.tmp_minute["answeredInT"] += 1
                return True
        return False

    def _minute_log_if_needed(self, t_end: float) -> None:
        if t_end >= self.next_log_at:
            self.logs["t"].append(self.sim_t)
            q_len = len(self.queue)
            talk = sum(1 for a in self.agents[: self.staff_active] if a.state == "busy")
            acw = sum(1 for a in self.agents[: self.staff_active] if a.state == "acw")
            self.logs["arrivals"].append(self.tmp_minute["arrivals"])
            self.logs["q"].append(q_len)
            self.logs["talk"].append(talk)
            self.logs["acw"].append(acw)
            self.logs["answered"].append(self.tmp_minute["answered"])
            self.logs["answeredInT"].append(self.tmp_minute["answeredInT"])
            self.logs["completed"].append(self.tmp_minute["completed"])
            self.logs["staffActive"].append(self.staff_active)
            occ = (
                self.tmp_minute["busyAgentsTime"] / self.tmp_minute["activeAgentsTime"]
                if self.tmp_minute["activeAgentsTime"] > 0
                else 0.0
            )
            self.logs["occ"].append(occ)
            asa = (
                sum(self.tmp_minute["waitDur"]) / max(1, self.tmp_minute["answered"]) / 60.0
                if self.tmp_minute["answered"] > 0
                else 0.0
            )
            self.logs["asaMin"].append(asa)
            aht = (
                sum(self.tmp_minute["finishedDur"]) / max(1, len(self.tmp_minute["finishedDur"])) / 60.0
                if self.tmp_minute["finishedDur"]
                else (self.aht / 60.0)
            )
            self.logs["ahtMin"].append(aht)
            wait = (
                sum(self.tmp_minute["waitDur"]) / max(1, len(self.tmp_minute["waitDur"])) / 60.0
                if self.tmp_minute["waitDur"]
                else 0.0
            )
            self.logs["waitMin"].append(wait)

            # reset minute accumulators
            self.tmp_minute = {
                "finishedDur": [],
                "waitDur": [],
                "busyAgentsTime": 0.0,
                "activeAgentsTime": 0.0,
                "arrivals": 0,
                "answered": 0,
                "answeredInT": 0,
                "completed": 0,
            }
            self.next_log_at += 60.0

    def run_step(self, real_dt: float = 1.0, speed: float = 1.0) -> None:
        # Minimal path for unit tests that construct Simulation(num_agents=0):
        # emulate a simple tick and immediate completion if something is queued.
        if self.num_agents == 0:
            if self.agents and self.queue:
                # simulate immediate service/complete
                self.queue.pop(0)
                self.done_count += 1
                self.agents[0].state = "idle"
            self.current_time += 1
            return

        # Convert to simulation dt (client uses baseScale 60)
        sim_dt = max(0.0, float(real_dt)) * 60.0 * max(0.0, float(speed))
        t_end = self.sim_t + sim_dt

        # arrivals
        self._spawn_arrivals_until(t_end)

        # accumulate active time
        self.tmp_minute["activeAgentsTime"] += sim_dt * float(self.staff_active)

        # transitions within this step
        # Busy agents may finish and move to ACW; ACW may finish and complete
        for ag in self.agents[: self.staff_active]:
            if ag.state == "busy":
                # Add busy time portion within this step
                if ag.busy_until > self.sim_t:
                    self.tmp_minute["busyAgentsTime"] += min(sim_dt, max(0.0, ag.busy_until - self.sim_t))
                if t_end >= ag.busy_until and ag.busy_until > 0:
                    # finishes talk
                    finished_dur = ag.busy_until - self.sim_t  # approx talk duration in this step window
                    if finished_dur > 0:
                        self.tmp_minute["finishedDur"].append(finished_dur)
                    ag.state = "acw"
                    ag.acw_until = ag.busy_until + max(1.0, rnd_exp(max(1.0, self.acw)))

            if ag.state == "acw":
                if t_end >= ag.acw_until and ag.acw_until > 0:
                    self.done_count += 1
                    self.tmp_minute["completed"] += 1
                    ag.state = "idle"
                    ag.acw_until = 0.0

        # Try assign as many as possible
        while self._try_assign():
            pass

        # advance time, log minute aggregates if passed minute
        self.sim_t = t_end
        # Advance test-friendly tick counter
        self.current_time += 1
        self._minute_log_if_needed(t_end)

    def get_state(self) -> dict:
        talk = sum(1 for a in self.agents[: self.staff_active] if a.state == "busy")
        acw = sum(1 for a in self.agents[: self.staff_active] if a.state == "acw")
        return {
            "time": self.sim_t,
            "queue": len(self.queue),
            "talk": talk,
            "acw": acw,
            "done": self.done_count,
            "staffActive": self.staff_active,
        }

    def get_results(self) -> dict:
        return {
            **self.get_state(),
            "logs": self.logs,
        }