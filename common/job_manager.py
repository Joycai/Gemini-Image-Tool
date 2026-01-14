import asyncio
from dataclasses import dataclass, field
from typing import Callable, Any, Dict, Optional
import traceback

@dataclass
class Job:
    id: str
    task_func: Callable
    kwargs: Dict[str, Any]
    on_start: Optional[Callable] = None
    on_success: Optional[Callable] = None
    on_error: Optional[Callable] = None
    on_finally: Optional[Callable] = None

class JobManager:
    def __init__(self):
        self.queue = asyncio.Queue()
        self._worker_task = None
        self.current_job_id = None

    async def start_worker(self):
        """Starts the background worker if it's not already running."""
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def _worker_loop(self):
        while True:
            job: Job = await self.queue.get()
            self.current_job_id = job.id
            try:
                if job.on_start:
                    if asyncio.iscoroutinefunction(job.on_start):
                        await job.on_start()
                    else:
                        job.on_start()

                # Execute the task in a thread pool since it's likely blocking (API call)
                result = await asyncio.to_thread(job.task_func, **job.kwargs)

                if job.on_success:
                    if asyncio.iscoroutinefunction(job.on_success):
                        await job.on_success(result)
                    else:
                        job.on_success(result)
            except Exception as e:
                print(f"Error executing job {job.id}: {e}")
                traceback.print_exc()
                if job.on_error:
                    if asyncio.iscoroutinefunction(job.on_error):
                        await job.on_error(str(e))
                    else:
                        job.on_error(str(e))
            finally:
                if job.on_finally:
                    if asyncio.iscoroutinefunction(job.on_finally):
                        await job.on_finally()
                    else:
                        job.on_finally()
                self.queue.task_done()
                self.current_job_id = None

    async def add_job(self, job: Job):
        await self.queue.put(job)
        await self.start_worker()

    def get_queue_size(self):
        return self.queue.qsize()

# Global instance
job_manager = JobManager()
