from flask import Flask, request, jsonify, send_from_directory
import os

app = Flask(__name__, static_folder='../web')

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/start', methods=['POST'])
def start_simulation():
    # Logic to start the simulation
    return jsonify({"status": "Simulation started"})

@app.route('/api/stop', methods=['POST'])
def stop_simulation():
    # Logic to stop the simulation
    return jsonify({"status": "Simulation stopped"})

@app.route('/api/reset', methods=['POST'])
def reset_simulation():
    # Logic to reset the simulation
    return jsonify({"status": "Simulation reset"})

@app.route('/api/results', methods=['GET'])
def get_results():
    # Logic to retrieve simulation results
    return jsonify({"results": "Simulation results here"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)