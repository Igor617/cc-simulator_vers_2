from flask import Flask, request, jsonify
from .sim import Simulation

app = Flask(__name__)
simulation = None

@app.route('/api/start', methods=['POST'])
def start_simulation():
    global simulation
    if simulation is None:
        simulation = Simulation()
        simulation.start()
        return jsonify({"status": "Simulation started"}), 200
    else:
        return jsonify({"status": "Simulation is already running"}), 400

@app.route('/api/stop', methods=['POST'])
def stop_simulation():
    global simulation
    if simulation is not None:
        simulation.stop()
        simulation = None
        return jsonify({"status": "Simulation stopped"}), 200
    else:
        return jsonify({"status": "No simulation is running"}), 400

@app.route('/api/reset', methods=['POST'])
def reset_simulation():
    global simulation
    if simulation is not None:
        simulation.reset()
        return jsonify({"status": "Simulation reset"}), 200
    else:
        return jsonify({"status": "No simulation to reset"}), 400

@app.route('/api/results', methods=['GET'])
def get_results():
    global simulation
    if simulation is not None:
        results = simulation.get_results()
        return jsonify(results), 200
    else:
        return jsonify({"status": "No simulation is running"}), 400

if __name__ == '__main__':
    app.run(debug=True)