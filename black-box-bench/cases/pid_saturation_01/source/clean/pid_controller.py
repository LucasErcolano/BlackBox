"""Toy PID controller for a differential-drive robot (CLEAN)."""

import time


PWM_MAX = 255
PWM_MIN = 0


class PIDController:
    def __init__(self, kp: float = 1.2, ki: float = 0.4, kd: float = 0.05):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.integral = 0.0
        self.prev_err = 0.0
        self.prev_t = None

    def reset(self) -> None:
        self.integral = 0.0
        self.prev_err = 0.0
        self.prev_t = None

    def step(self, setpoint: float, measured: float) -> float:
        now = time.time()
        dt = 0.02 if self.prev_t is None else max(1e-3, now - self.prev_t)
        err = setpoint - measured

        # Tentative integral and output
        tentative_integral = self.integral + err * dt
        derivative = (err - self.prev_err) / dt
        u = self.kp * err + self.ki * tentative_integral + self.kd * derivative
        u_cmd = max(PWM_MIN, min(PWM_MAX, u))

        # Anti-windup: only accumulate when not saturated (or when err pushes away from rail)
        saturated_high = u >= PWM_MAX and err > 0
        saturated_low = u <= PWM_MIN and err < 0
        if not (saturated_high or saturated_low):
            self.integral = tentative_integral

        self.prev_err = err
        self.prev_t = now
        return u_cmd
