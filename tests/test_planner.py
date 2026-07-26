"""Tests for the task planner."""

from core.planner import PlanStep, TaskPlan


class TestPlanStep:
    def test_plan_step_creation(self):
        step = PlanStep(step_number=1, agent="executor", action="test", expected_outcome="done")
        assert step.step_number == 1
        assert step.agent == "executor"
        assert step.action == "test"


class TestTaskPlan:
    def test_task_plan_creation(self):
        step = PlanStep(step_number=1, agent="executor", action="test", expected_outcome="done")
        plan = TaskPlan(objective="test objective", steps=[step])
        assert plan.objective == "test objective"
        assert len(plan.steps) == 1
