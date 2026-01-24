import asyncio
import inspect
from dataclasses import dataclass, field
from typing import Callable, Any, Dict, Optional, List
import traceback
import time
import threading
import ctypes

class JobInterruptError(BaseException):
    """
    Custom exception used to interrupt a running job thread.
    Inherits from BaseException so it is NOT caught by 'except Exception' blocks
    in the API client retry loops.
    """
    pass

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
        self._current_thread = None
        self._interrupt_event = asyncio.Event()

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
            try:
                res = func(*args, **kwargs)
                if inspect.isawaitable(res):
                    await res
            except Exception as e:
                print(f"Error in callback: {e}")

    async def start_worker(self):
        """Starts the background worker if it's not already running."""
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def _worker_loop(self):
        while True:
            job: Job = await self.queue.get()
            self._interrupt_event.clear()
            
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

                def thread_wrapper():
                    self._current_thread = threading.current_thread()
                    try:
                        return job.task_func(**job.kwargs)
                    except JobInterruptError:
                        # Silently exit the thread if interrupted
                        return None
                    finally:
                        self._current_thread = None

                # Run the thread task in a way we can "abandon" it if interrupted
                thread_task = asyncio.to_thread(thread_wrapper)
                
                # Wait for either the task to finish OR the interrupt event to fire
                done, pending = await asyncio.wait(
                    [asyncio.create_task(thread_task), asyncio.create_task(self._interrupt_event.wait())],
                    return_when=asyncio.FIRST_COMPLETED
                )

                # Cancel the pending tasks (the event wait or the thread task)
                for task in pending:
                    task.cancel()

                if self._interrupt_event.is_set():
                    # Interrupted!
                    job.status = "cancelled"
                    job.error = "Interrupted by user"
                else:
                    # Task finished normally
                    result = await list(done)[0] # Get the result from the thread_task
                    if job.status != "cancelled":
                        job.status = "success"
                        await self._maybe_await(job.on_success, result)

            except Exception as e:
                if job.status == "cancelled":
                    pass
                else:
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
        if len(self.history) > 50:
            self.history.pop(0)
        await self.queue.put(job)
        self._notify()
        await self.start_worker()

    def interrupt_current_job(self):
        """Forcefully interrupts the currently running job."""
        if self.current_job and self.current_job.status == "running":
            self.current_job.status = "cancelled"
            
            # 1. Signal the worker loop to stop waiting for the thread
            self._interrupt_event.set()
            
            # 2. Try to break the thread (best effort)
            if self._current_thread:
                thread_id = self._current_thread.ident
                if thread_id:
                    # Injecting BaseException ensures it bypasses 'except Exception'
                    ctypes.pythonapi.PyThreadState_SetAsyncExc(
                        ctypes.c_long(thread_id), 
                        ctypes.py_object(JobInterruptError)
                    )
            
            self._notify()
            return True
        return False

    def cancel_job(self, job_id: str):
        if self.current_job and self.current_job.id == job_id:
            return self.interrupt_current_job()
            
        for job in self.history:
            if job.id == job_id and job.status == "queued":
                self._cancelled_ids.add(job_id)
                job.status = "cancelled"
                self._notify()
                return True
        return False

    def get_queue_size(self):
        count = 0
        for job in self.history:
            if job.status == "queued":
                count += 1
        return count

    def get_all_jobs(self) -> List[Job]:
        return self.history

# Global instance
job_manager = JobManager()
