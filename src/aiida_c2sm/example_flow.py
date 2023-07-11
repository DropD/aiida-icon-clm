import time

from aiida import engine, orm
from aiida.engine.processes.workchains import context, workchain


@engine.calcfunction
def hello(task_name: str) -> orm.Str:
    time.sleep(5)
    return orm.Str(f"Hello from {task_name}!")


class Hello(engine.WorkChain):
    @classmethod
    def define(cls: type, spec: workchain.WorkChainSpec) -> None:
        super().define(spec)
        spec.input("task_name")
        spec.input("sleep_duration", default=lambda: orm.Int(5))
        spec.outline(cls.say_hello)

    def say_hello(self) -> None:
        self.ctx.task_name = self.inputs.task_name.value
        time.sleep(self.inputs.sleep_duration.value)
        self.report(f"Hello from {self.ctx.task_name}")


class Minimal(engine.WorkChain):
    @classmethod
    def define(cls: type, spec: workchain.WorkChainSpec) -> None:
        super().define(spec)
        spec.outline(cls.run_a, cls.wait_for_a)

    def run_a(self) -> context.ToContext:
        a = self.submit(Hello, task_name=orm.Str("a"))
        return engine.ToContext(a=a)

    def wait_for_a(self) -> None:
        assert self.ctx.a.is_finished_ok


class DelayWait(engine.WorkChain):
    @classmethod
    def define(cls: type, spec: workchain.WorkChainSpec) -> None:
        super().define(spec)
        spec.outline(
            cls.init_ctx,
            cls.sub_a,
            cls.sub_b,
            cls.push_a,
            cls.await_a,
            cls.push_all,
            cls.await_all,
        )

    def init_ctx(self) -> None:
        self.ctx.all: list[str] = []

    def sub_a(self) -> None:
        a = self.submit(Hello, task_name=orm.Str("a"))
        self.report(f"Submitted a: {a.pk}")
        self.ctx.id_a = a.uuid
        self.ctx.all.append(a.uuid)

    def sub_b(self) -> None:
        b = self.submit(Hello, task_name=orm.Str("b"), sleep_duration=orm.Int(10))
        self.report(f"Submitted b: {b.pk}")
        self.ctx.id_b = b.uuid
        self.ctx.all.append(b.uuid)

    def push_a(self) -> None:
        self.ctx.all.remove(self.ctx.id_a)
        self.to_context(node_a=orm.WorkChainNode.get(uuid=self.ctx.id_a))
        self.report("Pushed a")

    def await_a(self) -> None:
        assert self.ctx.node_a.is_finished_ok
        self.report("Awaited a")

    def push_all(self) -> None:
        for wf_id in self.ctx.all:
            wf = orm.WorkChainNode.get(uuid=wf_id)
            self.to_context(pending=engine.append_(wf))
            self.report(f"Pushed {wf.inputs.task_name.value}")

    def await_all(self) -> None:
        for wf in self.ctx.pending:
            assert wf.is_finished_ok
            self.report(f"Awaited {wf.inputs.task_name.value}")


class WaitingHello(engine.WorkChain):
    @classmethod
    def define(cls: type, spec: workchain.WorkChainSpec) -> None:
        super().define(spec)
        spec.input("dependencies")
        spec.expose_inputs(Hello)
        spec.outline(
            cls.push_dependencies, cls.await_dependencies, cls.hello, cls.await_hello
        )

    def push_dependencies(self) -> None:
        for i in self.inputs.dependencies.get_list():
            self.report(f"Pushing {i}")
            self.to_context(
                pending_dependencies=engine.append_(orm.WorkChainNode.get(uuid=i))
            )

    def await_dependencies(self) -> None:
        for wf in self.ctx.pending_dependencies:
            self.report(f"Checking {wf.uuid}")
            assert wf.is_finished_ok

    def hello(self) -> None:
        self.report("Starting Hello")
        self.to_context(hello=self.submit(Hello, **self.exposed_inputs(Hello)))

    def await_hello(self) -> None:
        assert self.ctx.hello.is_finished_ok
        self.report("Done Helloing")


class HandoffWait(engine.WorkChain):
    @classmethod
    def define(cls: type, spec: workchain.WorkChainSpec) -> None:
        super().define(spec)
        spec.outline(
            cls.sub_a,
            cls.sub_b,
            cls.sub_c,
            cls.sub_d,
            cls.await_d,
        )

    def sub_a(self) -> None:
        a = self.submit(Hello, task_name=orm.Str("A"))
        self.report(f"Subbing A: {a.pk}")
        self.ctx.id_a = a.uuid

    def sub_b(self) -> None:
        b = self.submit(
            WaitingHello,
            task_name=orm.Str("B"),
            dependencies=orm.List(list=[self.ctx.id_a]),
            sleep_duration=orm.Int(10),
        )
        self.report(f"Subbing B: {b.pk}")
        self.ctx.id_b = b.uuid

    def sub_c(self) -> None:
        c = self.submit(
            WaitingHello,
            task_name=orm.Str("C"),
            dependencies=orm.List(list=[self.ctx.id_a]),
            sleep_duration=orm.Int(2),
        )
        self.report(f"Subbing C: {c.pk}")
        self.ctx.id_c = c.uuid

    def sub_d(self) -> None:
        d = self.submit(
            WaitingHello,
            task_name=orm.Str("D"),
            dependencies=orm.List(list=[self.ctx.id_b, self.ctx.id_c]),
        )
        self.report(f"Subbing D: {d.pk}")
        self.to_context(d=d)

    def await_d(self) -> None:
        assert self.ctx.d.is_finished_ok
        self.report("Done")


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
