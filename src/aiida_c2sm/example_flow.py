import time

from aiida import engine, orm
from aiida.engine.processes.workchains import workchain


@engine.calcfunction
def hello(task_name: str) -> orm.Str:
    time.sleep(5)
    return orm.Str(f"Hello from {task_name}!")


class Minimal(engine.WorkChain):
    @classmethod
    def define(cls: type, spec: workchain.WorkChainSpec) -> None:
        super().define(spec)
        spec.outline(cls.run_a, cls.wait_for_a)

    def run_a(self) -> None:
        a = self.submit(hello, task_name="a")
        engine.ToContext(a=a)

    def wait_for_a(self) -> None:
        assert self.ctx.a.is_finished_ok


class P1(engine.WorkChain):
    @classmethod
    def define(cls: type, spec: workchain.WorkChainSpec) -> None:
        super().define(spec)
        spec.input("cycle_point")
        spec.input("previous_b_pk")
        spec.output("b_pk")
        spec.outline(
            cls.init,
            cls.run_a,
            cls.wait_for_previous_b,
            cls.run_b,
            cls.run_c_and_d,
            cls.wait_for_child,
            cls.check_child,
        )

    def init_cycle_point(self) -> None:
        self.ctx.cycle_point = self.inputs.cycle_point or 1
        self.ctx.next_pk = []

    def run_a(self) -> None:
        node = self.submit(hello, {"task_name": "a"})
        engine.ToContext(a=node)

    def wait_for_previous_b(self) -> None:
        prev_b = orm.WorkChainNode.get(pk=self.inputs.previous_b_pk)
        engine.ToContext(**{"b[-P1]": prev_b})

    def run_b(self) -> None:
        assert self.ctx.a.is_finished_ok
        assert self.ctx["b[-P1]"].is_finished_ok
        b = self.submit(hello, {"task_name": "b"})
        next_point = self.submit(
            P1, {"cycle_point": self.ctx.cycle_point + 1, "previous_b_pk": b.pk}
        )
        self.ctx.next_pk = next_point.pk
        engine.ToContext(b=b)

    def run_c_and_d(self) -> None:
        assert self.ctx.b.is_finished_ok
        self.submit(hello, {"task_name": "c"})
        self.submit(hello, {"task_name": "d"})

    def wait_for_children(self) -> None:
        next_wc = orm.WorkChainNode.get(pk=self.ctx.next_pk)
        engine.ToContext(child=next_wc)

    def check_child(self) -> None:
        self.ctx.child.is_finished_ok


class CyclingWorkflow(engine.WorkChain):
    @classmethod
    def define(cls: type, spec: workchain.WorkChainSpec) -> None:
        super().define(spec)
        spec.input("initial_cycle_point")
        spec.input("final_cycle_point")
        spec.outline(
            cls.init,
            engine.while_(cls.should_run)(cls.submit_a, cls.submit_b, cls.submit_cd),
        )
