# Contents of the file: /cc-simulator/cc-simulator/src/cc_simulator/sim.py

import random
import math
from collections import deque

class Agent:
    def __init__(self, id):
        self.id = id
        self.state = 'idle'
        self.busy_until = 0
        self.acw_until = 0

class Simulation:
    def __init__(self, lambda_rate, aht, acw, sla, threshold, occ_max, shrink, num_agents):
        self.lambda_rate = lambda_rate
        self.aht = aht
        self.acw = acw
        self.sla = sla
        self.threshold = threshold
        self.occ_max = occ_max
        self.shrink = shrink
        self.num_agents = num_agents
        self.agents = [Agent(i) for i in range(num_agents)]
        self.queue = deque()
        self.sim_time = 0
        self.done_count = 0
        self.logs = {
            'time': [],
            'arrivals': [],
            'queue_length': [],
            'active_agents': [],
            'completed': []
        }
        self.next_arrival = 0

    def run_step(self, real_dt):
        sim_dt = real_dt * 60  # Scale real time to simulation time
        self.sim_time += sim_dt
        self.handle_arrivals()
        self.update_agents()
        self.log_metrics()

    def handle_arrivals(self):
        while self.next_arrival <= self.sim_time:
            self.queue.append(self.sim_time)
            self.next_arrival += self.random_exponential(1 / (self.lambda_rate / 3600))

    def update_agents(self):
        for agent in self.agents:
            if agent.state == 'busy' and self.sim_time >= agent.busy_until:
                agent.state = 'acw'
                agent.acw_until = self.sim_time + self.random_exponential(self.acw)

            if agent.state == 'acw' and self.sim_time >= agent.acw_until:
                agent.state = 'idle'
                self.done_count += 1
                self.queue.popleft()  # Remove from queue when done

            if agent.state == 'idle' and self.queue:
                agent.state = 'busy'
                agent.busy_until = self.sim_time + self.random_exponential(self.aht)

    def random_exponential(self, mean):
        return -mean * math.log(1 - random.random())

    def log_metrics(self):
        self.logs['time'].append(self.sim_time)
        self.logs['arrivals'].append(len(self.queue))
        self.logs['active_agents'].append(sum(agent.state == 'busy' for agent in self.agents))
        self.logs['completed'].append(self.done_count)

    def reset(self):
        self.queue.clear()
        self.sim_time = 0
        self.done_count = 0
        self.logs = {key: [] for key in self.logs.keys()}
        self.agents = [Agent(i) for i in range(self.num_agents)]

    def get_results(self):
        return self.logs