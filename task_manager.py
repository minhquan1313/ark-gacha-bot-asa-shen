import heapq
import json
import time
from itertools import count
from threading import Lock

import source.gacha_bot.stations as stations
import source.logs.gachalogs as logs
from source.gacha_bot.craft_config import load_craft_config, valid_craft_route

global scheduler
global started
scheduler = None
started = False


class SingletonMeta(type):
    _instances = {}

    _lock: Lock = Lock()

    def __call__(cls, *args, **kwargs):

        with cls._lock:
            if cls not in cls._instances:
                instance = super().__call__(*args, **kwargs)
                cls._instances[cls] = instance
        return cls._instances[cls]


# next exe time, insertion sequence, priority, the task
WaitingTaskItem = tuple[float, int, int, stations.BaseTask]
# priority, next exe time, insertion sequence, the task
ActiveTaskItem = tuple[int, float, int, stations.BaseTask]


class PriorityQueueWait:
    def __init__(self):
        self.queue: list[WaitingTaskItem] = []
        self._sequence = count()

    def add(self, task: stations.BaseTask, priority: int, execution_time: float):
        heapq.heappush(self.queue, (execution_time, next(self._sequence), priority, task))

    def pop(self):
        if not self.is_empty():
            return heapq.heappop(self.queue)
        return None

    def peek(self):
        if not self.is_empty():
            return self.queue[0]
        return None

    def is_empty(self):
        return len(self.queue) == 0


class PriorityQueueReady:
    def __init__(self):
        self.queue: list[ActiveTaskItem] = []
        self._sequence = count()

    def add(self, task: stations.BaseTask, priority: int, execution_time: float):
        heapq.heappush(self.queue, (priority, execution_time, next(self._sequence), task))

    def pop(self):
        if not self.is_empty():
            return heapq.heappop(self.queue)
        return None

    def peek(self):
        if not self.is_empty():
            return self.queue[0]
        return None

    def is_empty(self):
        return len(self.queue) == 0


class task_scheduler(metaclass=SingletonMeta):
    def __init__(self):
        if not hasattr(self, "initialized"):
            self.active_queue = PriorityQueueReady()
            self.waiting_queue = PriorityQueueWait()
            self.initialized = True
            self.prev_task_name = ""
            self.running_task = None

    def emit_queue_snapshot(self):
        waiting = [
            #
            {"name": task.name, "execution_time": exec_time, "state": "WAITING"}
            for exec_time, _, _, task in sorted(self.waiting_queue.queue)
        ]
        active = [
            #
            {"name": task.name, "execution_time": exec_time, "state": "READY"}
            for _, exec_time, _, task in sorted(self.active_queue.queue)
        ]
        running = (
            [
                #
                {"name": self.running_task.name, "state": "RUNNING"}
            ]
            if self.running_task is not None
            else []
        )
        print(
            f"[QUEUE_STATE] {json.dumps({'running': running, 'active': active, 'waiting': waiting})}",
            flush=True,
        )

    def add_task(self, task: stations.BaseTask):
        next_execution_time = (
            time.time()
            #
            if not getattr(task, "has_run_before", False)
            else time.time() + task.get_requeue_delay()
        )

        task.has_run_before = True

        self.waiting_queue.add(task, task.get_priority_level(), next_execution_time)
        print(f"Added task {task.name} to waiting queue ")  # might need to remove this if you have LOADS OF stations causing long messages
        self.emit_queue_snapshot()

    def run(self):
        time.sleep(0.2)  # Allow time for the main thread to focus to ark first(in case of main menu, player not joined server yet)
        while True:
            current_time = time.time()

            self.move_ready_tasks_to_active_queue(current_time)

            if not self.active_queue.is_empty():
                self.execute_task(current_time)
            else:
                time.sleep(5)

    def move_ready_tasks_to_active_queue(self, current_time):
        while not self.waiting_queue.is_empty():
            task_tuple = self.waiting_queue.peek()
            if task_tuple is None:
                break
            exec_time, _, priority, task = task_tuple

            if exec_time <= current_time:
                self.waiting_queue.pop()
                self.active_queue.add(task, priority, exec_time)

            else:
                break
        self.emit_queue_snapshot()

    def execute_task(self, current_time):

        task_tuple = self.active_queue.pop()
        if task_tuple is None:
            return
        priority, exec_time, _, task = task_tuple

        if exec_time <= current_time:
            if task.name != self.prev_task_name:
                logs.logger.info(f"Executing task: {task.name}")
            self.running_task = task
            self.emit_queue_snapshot()
            task.execute()

            self.prev_task_name = task.name
            self.running_task = None
            self.move_to_waiting_queue(task)
        else:
            self.active_queue.add(task, priority, exec_time)

    def move_to_waiting_queue(self, task):
        logs.logger.debug(f"adding {task.name} to waiting queue")
        next_execution_time = time.time() + task.get_requeue_delay()
        priority_level = task.get_priority_level()
        self.waiting_queue.add(task, priority_level, next_execution_time)
        self.emit_queue_snapshot()


def load_resolution_data(file_path):
    try:
        with open(file_path, "r") as file:
            data = file.read().strip()
            if not data:
                logs.logger.warning(f"warning: {file_path} is empty no tasks added.")
                return []
            return json.loads(data)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"error loading JSON from {file_path}: {e}")
        return []


def prepare():
    """Load configured tasks and publish their initial queue without running them."""
    global scheduler
    scheduler = task_scheduler()

    pego_data = load_resolution_data("json_files/pego.json")
    for index, entry_pego in enumerate(pego_data):
        teleporter = entry_pego["teleporter"]
        delay = entry_pego["delay"]
        task = stations.PegoStation(index, teleporter, delay)
        scheduler.add_task(task)

    gacha_data = load_resolution_data("json_files/gacha.json")
    for entry_gacha in gacha_data:
        if not str(entry_gacha["teleporter"]).strip():
            continue
        teleporter = entry_gacha["teleporter"]
        direction = entry_gacha["side"]
        task = stations.GachaStation(teleporter, direction)
        scheduler.add_task(task)

    collect_data = load_resolution_data("json_files/gacha_collect.json")
    for entry in collect_data:
        teleporter = entry.get("teleporter", "")
        if teleporter.strip():
            direction = entry.get("side", "left")
            scheduler.add_task(
                stations.GachaCollectStation(
                    teleporter,
                    direction,
                    entry.get("item", ""),
                    entry.get("dedi_teleport", ""),
                )
            )

    for index, route in enumerate(load_craft_config()["generalCraftData"]):
        if valid_craft_route(route):
            scheduler.add_task(stations.CraftStation(route, index))
        else:
            logs.logger.warning(f"Skipping craft entry {index + 1}: configure teleport, item, and output dedis.")

    scheduler.add_task(stations.RenderStation())
    logs.logger.info("scheduler prepared")
    return scheduler


def run():
    """Start the scheduler loop after task preparation is complete."""
    global scheduler
    global started
    if scheduler is None:
        scheduler = prepare()
    logs.logger.info("scheduler now running")
    started = True
    scheduler.run()


def main():
    """Prepare configured tasks and start the scheduler loop."""
    prepare()
    run()


if __name__ == "__main__":
    time.sleep(2)
    main()
