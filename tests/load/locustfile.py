"""
tests/load/locustfile.py

Realistic load test simulating full user journey.

Run:
    locust -f tests/load/locustfile.py --host=http://localhost:8000

Then open http://localhost:8089 for the dashboard.

Scenarios:
- 80% of users: register → login → list jobs (read-heavy)
- 20% of users: register → login → upload → poll status
"""

import io
import random
import string
import time

from locust import HttpUser, between, task


def random_email() -> str:
    suffix = "".join(random.choices(string.ascii_lowercase, k=8))
    return f"loadtest_{suffix}@example.com"


class STTPlatformUser(HttpUser):
    wait_time = between(1, 3)
    token: str = ""
    job_ids: list[str] = []

    def on_start(self) -> None:
        """Called once per simulated user on startup."""
        email = random_email()
        password = "loadtest123"

        # Register
        self.client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password},
            name="/auth/register",
        )

        # Login
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
            name="/auth/login",
        )
        if resp.status_code == 200:
            self.token = resp.json().get("access_token", "")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    @task(5)
    def list_jobs(self) -> None:
        self.client.get(
            "/api/v1/transcriptions/",
            headers=self._headers(),
            name="/transcriptions/",
        )

    @task(3)
    def get_profile(self) -> None:
        self.client.get(
            "/api/v1/auth/me",
            headers=self._headers(),
            name="/auth/me",
        )

    @task(1)
    def upload_audio(self) -> None:
        # Fake audio bytes — just testing API throughput, not transcription
        fake_audio = io.BytesIO(b"\x00" * 1024 * 100)  # 100KB
        resp = self.client.post(
            "/api/v1/transcriptions/upload",
            headers=self._headers(),
            files={"file": ("test.mp3", fake_audio, "audio/mpeg")},
            name="/transcriptions/upload",
        )
        if resp.status_code == 202:
            job_id = resp.json().get("id")
            if job_id:
                self.job_ids.append(job_id)

    @task(2)
    def poll_job_status(self) -> None:
        if not self.job_ids:
            return
        job_id = random.choice(self.job_ids)
        self.client.get(
            f"/api/v1/transcriptions/{job_id}",
            headers=self._headers(),
            name="/transcriptions/{job_id}",
        )

    @task(1)
    def health_check(self) -> None:
        self.client.get("/api/v1/health", name="/health")