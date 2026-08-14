from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import hashlib
import json
from threading import Lock
from typing import Any, Callable, Mapping, Sequence

from .diagnostics import TevScriptError
from .ir_v4_pure import MAX_PURE_TASKS_V4, PrioritySelectCandidateOutcomeV4, TaskChildEvaluationV4

MAX_TASK_WORKERS_V2 = MAX_PURE_TASKS_V4
TASK_SCHEDULER_POLICY_V2 = "fork_local_budget_join_sum_v1"


@dataclass(frozen=True, slots=True)
class BoundedThreadTaskStrategyV2:
    worker_count: int = 4

    def __post_init__(self) -> None:
        if isinstance(self.worker_count, bool) or not isinstance(self.worker_count, int) or not 1 <= self.worker_count <= MAX_TASK_WORKERS_V2:
            raise TevScriptError(
                "TEVS_V2_TASK_SCHEDULER_WORKERS",
                f"worker_count must be 1..{MAX_TASK_WORKERS_V2}",
            )

    def descriptor(self) -> dict[str, Any]:
        payload = {
            "schema": "TEV_SCRIPT_V2_TASK_SCHEDULER_DESCRIPTOR_R1",
            "strategy": "bounded_thread_pool_v1",
            "worker_count": self.worker_count,
            "semantic_policy": TASK_SCHEDULER_POLICY_V2,
            "worker_count_is_semantic": False,
            "task_side_effects": False,
            "structured_join_required": True,
            "priority_select_speculation": True,
            "select_observation_policy": "priority_order_v1",
            "select_semantic_accounting": "reference_prefix_v1",
            "nested_select_candidate_task_scheduling": "sequential_v1",
            "select_cancellation_policy": "cooperative_lower_priority_only_v1",
            "select_terminal_authority": "kernel_priority_prefix_v1",
        }
        payload["descriptor_hash"] = _hash(payload)
        return payload

    def run(
        self,
        tasks: Sequence[Mapping[str, Any]],
        evaluate_child: Callable[[Mapping[str, Any]], TaskChildEvaluationV4],
    ) -> Sequence[TaskChildEvaluationV4]:
        task_tuple = tuple(tasks)
        if not 1 <= len(task_tuple) <= MAX_PURE_TASKS_V4:
            raise TevScriptError(
                "TEVS_V2_TASK_SCHEDULER_BOUND",
                f"scheduler requires 1..{MAX_PURE_TASKS_V4} child tasks",
            )
        if self.worker_count == 1 or len(task_tuple) == 1:
            return tuple(evaluate_child(task) for task in task_tuple)

        workers = min(self.worker_count, len(task_tuple))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="tev-task-v2") as executor:
            futures = tuple(executor.submit(evaluate_child, task) for task in task_tuple)
            completed: list[TaskChildEvaluationV4] = []
            try:
                # Futures are observed in canonical task order, not completion order.
                # This preserves the reference evaluator's fail-closed diagnostic.
                for future in futures:
                    completed.append(future.result())
            except Exception:
                for future in futures[len(completed) + 1:]:
                    future.cancel()
                raise
        return tuple(completed)

    def run_select_cooperative(
        self,
        candidates: Sequence[tuple[int, Mapping[str, Any]]],
        evaluate_candidate: Callable[[tuple[int, Mapping[str, Any]], Callable[[], bool]], PrioritySelectCandidateOutcomeV4],
        is_terminal: Callable[[tuple[int, Mapping[str, Any]], PrioritySelectCandidateOutcomeV4], bool],
    ) -> Sequence[PrioritySelectCandidateOutcomeV4]:
        candidate_tuple=tuple(candidates)
        if not 1<=len(candidate_tuple)<=MAX_PURE_TASKS_V4:
            raise TevScriptError(
                "TEVS_V2_TASK_SCHEDULER_SELECT_BOUND",
                f"cooperative select requires 1..{MAX_PURE_TASKS_V4} candidates",
            )
        indexes=tuple(index for index,_candidate in candidate_tuple)
        if indexes!=tuple(range(len(candidate_tuple))):
            raise TevScriptError(
                "TEVS_V2_TASK_SCHEDULER_SELECT_ORDER",
                "cooperative select candidates must use canonical contiguous priority indexes",
            )
        if self.worker_count==1 or len(candidate_tuple)==1:
            completed=[]
            for item in candidate_tuple:
                outcome=evaluate_candidate(item,lambda:False); completed.append(outcome)
                if is_terminal(item,outcome):
                    return tuple(completed)
            return tuple(completed)

        lock=Lock(); terminal_index: list[int | None]=[None]
        def cancelled(index: int) -> bool:
            with lock:
                terminal=terminal_index[0]
            return terminal is not None and index>terminal

        workers=min(self.worker_count,len(candidate_tuple))
        executor=ThreadPoolExecutor(max_workers=workers,thread_name_prefix="tev-select-v2")
        futures=tuple(
            executor.submit(
                evaluate_candidate,
                item,
                (lambda index=item[0]: cancelled(index)),
            )
            for item in candidate_tuple
        )
        completed: list[PrioritySelectCandidateOutcomeV4]=[]
        try:
            for position,(item,future) in enumerate(zip(candidate_tuple,futures,strict=True)):
                outcome=future.result(); completed.append(outcome)
                if is_terminal(item,outcome):
                    with lock:
                        terminal_index[0]=position
                    for lower in futures[position+1:]:
                        lower.cancel()
                    # Running lower-priority candidates see the cancellation probe
                    # on their next semantic budget consume and stop cooperatively.
                    for lower in futures[position+1:]:
                        if lower.cancelled():
                            continue
                        try:
                            lower.result()
                        except Exception:
                            pass
                    return tuple(completed)
            return tuple(completed)
        finally:
            executor.shutdown(wait=True,cancel_futures=True)

    def run_select(
        self,
        candidates: Sequence[tuple[int, Mapping[str, Any]]],
        evaluate_candidate: Callable[[tuple[int, Mapping[str, Any]]], PrioritySelectCandidateOutcomeV4],
    ) -> Sequence[PrioritySelectCandidateOutcomeV4]:
        candidate_tuple=tuple(candidates)
        if not 1<=len(candidate_tuple)<=MAX_PURE_TASKS_V4:
            raise TevScriptError(
                "TEVS_V2_TASK_SCHEDULER_SELECT_BOUND",
                f"select speculation requires 1..{MAX_PURE_TASKS_V4} candidates",
            )
        indexes=tuple(index for index,_candidate in candidate_tuple)
        if indexes!=tuple(range(len(candidate_tuple))):
            raise TevScriptError(
                "TEVS_V2_TASK_SCHEDULER_SELECT_ORDER",
                "select speculation candidates must use canonical contiguous priority indexes",
            )
        if self.worker_count==1 or len(candidate_tuple)==1:
            return tuple(evaluate_candidate(item) for item in candidate_tuple)
        workers=min(self.worker_count,len(candidate_tuple))
        with ThreadPoolExecutor(max_workers=workers,thread_name_prefix="tev-select-v2") as executor:
            futures=tuple(executor.submit(evaluate_candidate,item) for item in candidate_tuple)
            # Physical completion order has no authority. Outcomes are observed
            # and returned in semantic priority order.
            return tuple(future.result() for future in futures)


def _hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()
