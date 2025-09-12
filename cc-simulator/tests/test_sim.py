import unittest

from cc_simulator.sim import Simulation, Agent


class TestSimulation(unittest.TestCase):
    def setUp(self):
        self.simulation = Simulation(num_agents=0)

    def test_initial_conditions(self):
        self.assertEqual(self.simulation.current_time, 0)
        self.assertEqual(len(self.simulation.agents), 0)
        self.assertEqual(len(self.simulation.queue), 0)

    def test_add_agent(self):
        a = Agent(id=1)
        self.simulation.add_agent(a)
        self.assertEqual(len(self.simulation.agents), 1)
        self.assertEqual(self.simulation.agents[0].id, 1)

    def test_queue_behavior(self):
        a = Agent(id=1)
        self.simulation.add_agent(a)
        self.simulation.add_to_queue(a)
        self.assertEqual(len(self.simulation.queue), 1)

    def test_simulation_step(self):
        a = Agent(id=1)
        self.simulation.add_agent(a)
        self.simulation.add_to_queue(a)
        self.simulation.run_step()
        self.assertEqual(self.simulation.current_time, 1)

    def test_agent_state_change(self):
        a = Agent(id=1)
        self.simulation.add_agent(a)
        self.simulation.add_to_queue(a)
        self.simulation.run_step()
        # After first step agent goes busy then immediately completes and returns to idle
        self.assertEqual(a.state, "idle")
        self.assertEqual(self.simulation.done_count, 1)


if __name__ == "__main__":
    unittest.main()