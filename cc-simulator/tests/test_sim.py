import unittest
from src.cc_simulator.sim import Simulation
from src.cc_simulator.models import Agent, Queue

class TestSimulation(unittest.TestCase):

    def setUp(self):
        self.simulation = Simulation()
        self.agent = Agent(id=1, state='idle')
        self.queue = Queue()

    def test_initial_conditions(self):
        self.assertEqual(self.simulation.current_time, 0)
        self.assertEqual(len(self.simulation.agents), 0)
        self.assertEqual(len(self.simulation.queue), 0)

    def test_add_agent(self):
        self.simulation.add_agent(self.agent)
        self.assertEqual(len(self.simulation.agents), 1)
        self.assertEqual(self.simulation.agents[0].id, 1)

    def test_queue_behavior(self):
        self.simulation.add_to_queue(self.agent)
        self.assertEqual(len(self.simulation.queue), 1)
        self.assertEqual(self.simulation.queue[0].id, 1)

    def test_simulation_step(self):
        self.simulation.add_agent(self.agent)
        self.simulation.run_step()
        self.assertEqual(self.simulation.current_time, 1)  # Assuming each step increments time

    def test_agent_state_change(self):
        self.simulation.add_agent(self.agent)
        self.simulation.run_step()
        self.assertEqual(self.agent.state, 'busy')  # Assuming agent becomes busy after a step

if __name__ == '__main__':
    unittest.main()