# CC Simulator

## Overview
The CC Simulator is a 2D simulation model designed to simulate the operations of a call center. It allows users to input various parameters related to call handling, such as incoming call rates, average handling times, and staff availability. The simulation visualizes the flow of calls through the system, providing insights into performance metrics like wait times, service levels, and agent utilization.

## Project Structure
```
cc-simulator
├── src
│   └── cc_simulator
│       ├── __init__.py
│       ├── sim.py
│       ├── api.py
│       └── models.py
├── web
│   └── index.html
├── tests
│   └── test_sim.py
├── scripts
│   └── serve.py
├── pyproject.toml
├── .gitignore
├── Makefile
└── README.md
```

## Installation
To set up the project, follow these steps:

1. Clone the repository:
   ```
   git clone <repository-url>
   cd cc-simulator
   ```

2. Create a virtual environment (optional but recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage
To run the simulation:

1. Start the web server:
   ```
   python scripts/serve.py
   ```

2. Open your web browser and navigate to `http://localhost:8000` to access the simulation interface.

3. Input the desired parameters and start the simulation.

## Testing
To run the tests, use the following command:
```
pytest tests/test_sim.py
```

## Contributing
Contributions are welcome! Please submit a pull request or open an issue for any enhancements or bug fixes.

## License
This project is licensed under the MIT License. See the LICENSE file for more details.