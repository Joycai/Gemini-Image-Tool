import asyncio
import inspect
from dataclasses import dataclass, field
from typing import Callable, Any, Dict, Optional, List
import traceback
import time

@dataclass
class Job:
    id: str
    name: str
    task_func: Callable
    kwargs: Dict[str, Any]
    status: str = "queued" # queued, running, success, error, cancelled
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    error: Optional[str] = None
    on_start: Optional[Callable] = None
    on_success: Optional[Callable] = None
    on_error: Optional[Callable] = None
    on_finally: Optional[Callable] = None

class JobManager:
    def __init__(self):
        self.queue = asyncio.Queue()
        self._worker_task = None
        self.current_job: Optional[Job] = None
        self.history: List[Job] = [] # Keep track of recent jobs
        self._subscribers = []
        self._cancelled_ids = set()

    def subscribe(self, callback: Callable):
        self._subscribers.append(callback)

    def _notify(self):
        for cb in self._subscribers:
            try:
                cb()
            except:
                pass

    async def _maybe_await(self, func, *args, **kwargs):
        if func:
            res = func(*args, **kwargs)
            if inspect.isawaitable(res):
                await res

    async def start_worker(self):
        """Starts the background worker if it's not already running."""
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def _worker_loop(self):
        while True:
            job: Job = await self.queue.get()
            
            if job.id in self._cancelled_ids:
                job.status = "cancelled"
                job.finished_at = time.time()
                self._cancelled_ids.remove(job.id)
                self.queue.task_done()
                self._notify()
                continue

            self.current_job = job
            job.status = "running"
            job.started_at = time.time()
            self._notify()
            
            try:
                await self._maybe_await(job.on_start)

                # Execute the task in a thread pool since it's likely blocking (API call)
                result = await asyncio.to_thread(job.task_func, **job.kwargs)

                job.status = "success"
                await self._maybe_await(job.on_success, result)
            except Exception as e:
                job.status = "error"
                job.error = str(e)
                print(f"Error executing job {job.id}: {e}")
                traceback.print_exc()
                await self._maybe_await(job.on_error, str(e))
            finally:
                job.finished_at = time.time()
                await self._maybe_await(job.on_finally)
                self.queue.task_done()
                self.current_job = None
                self._notify()

    async def add_job(self, job: Job):
        self.history.append(job)
        if len(self.history) > 50: # Keep only last 50 jobs
            self.history.pop(0)
        await self.queue.put(job)
        self._notify()
        await self.start_worker()

    def cancel_job(self, job_id: str):
        """Marks a job as cancelled. If it's in the queue, it will be skipped."""
        for job in self.history:
            if job.id == job_id and job.status == "queued":
                self._cancelled_ids.add(job_id)
                job.status = "cancelled"
                self._notify()
                return True
        return False

    def get_queue_size(self):
        # Count only queued jobs that aren't marked for cancellation
        count = 0
        for job in self.history:
            if job.status == "queued":
                count += 1
        return count

    def get_all_jobs(self) -> List[Job]:
        return self.history

# Global instance
job_manager = JobManager()
