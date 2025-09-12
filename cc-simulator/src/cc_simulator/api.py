from __future__ import annotations

from flask import Flask, jsonify, request

from .sim import Simulation


class _SimHolder:
    sim: Simulation | None = None


def _get_sim() -> Simulation:
    if _SimHolder.sim is None:
        _SimHolder.sim = Simulation()
    return _SimHolder.sim


def _apply_params(sim: Simulation, data: dict) -> None:
    if not data:
        return
    sim.set_params(
        lambda_rate=float(data.get("lambda", getattr(sim, "lambda_rate", 360))),
        aht=float(data.get("aht", getattr(sim, "aht", 540))),
        acw=float(data.get("acw", getattr(sim, "acw", 60))),
        sla=float(data.get("sla", getattr(sim, "sla", 80))),
        thr=float(data.get("thr", getattr(sim, "thr", 20))),
        occ_max=float(data.get("occMax", getattr(sim, "occ_max", 85))),
        shrink=float(data.get("shrink", getattr(sim, "shrink", 20))),
        num_agents=int(data.get("N", getattr(sim, "num_agents", 12))),
    )


def register_routes(app: Flask) -> None:
    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.post("/api/start")
    def start_simulation():
        sim = _get_sim()
        data = request.get_json(silent=True) or {}
        _apply_params(sim, data)
        sim.reset()
        return jsonify({"status": "started", "state": sim.get_state()})

    @app.post("/api/stop")
    def stop_simulation():
        sim = _get_sim()
        sim.stop()
        return jsonify({"status": "stopped", "state": sim.get_state()})

    @app.post("/api/reset")
    def reset_simulation():
        sim = _get_sim()
        data = request.get_json(silent=True) or {}
        _apply_params(sim, data)
        sim.reset()
        return jsonify({"status": "reset", "state": sim.get_state()})

    @app.post("/api/step")
    def step():
        sim = _get_sim()
        payload = request.get_json(silent=True) or {}
        dt = float(payload.get("dt", 1.0))
        speed = float(payload.get("speed", 1.0))
        sim.run_step(dt, speed)
        return jsonify(sim.get_results())

    @app.get("/api/results")
    def results():
        sim = _get_sim()
        return jsonify(sim.get_results())