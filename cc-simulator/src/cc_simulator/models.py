class Agent:
    def __init__(self, agent_id, state='idle'):
        self.agent_id = agent_id
        self.state = state
        self.busy_until = 0
        self.acw_until = 0

class Queue:
    def __init__(self):
        self.customers = []

    def add_customer(self, customer):
        self.customers.append(customer)

    def remove_customer(self):
        if self.customers:
            return self.customers.pop(0)
        return None

class SimulationParameters:
    def __init__(self, lambda_rate, aht, acw, sla, threshold, occ_max, shrink, num_agents):
        self.lambda_rate = lambda_rate
        self.aht = aht
        self.acw = acw
        self.sla = sla
        self.threshold = threshold
        self.occ_max = occ_max
        self.shrink = shrink
        self.num_agents = num_agents

class SimulationState:
    def __init__(self):
        self.agents = []
        self.queue = Queue()
        self.done_count = 0
        self.sim_time = 0

    def add_agent(self, agent):
        self.agents.append(agent)

    def update_done_count(self):
        self.done_count += 1

    def reset(self):
        self.agents.clear()
        self.queue = Queue()
        self.done_count = 0
        self.sim_time = 0