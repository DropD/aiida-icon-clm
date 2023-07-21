from aiida import engine, orm, plugins
from aiida.engine.processes.workchains import workchain


class Dependencies(engine.WorkChain):
    """
    Start a dependent workchain after dependencies have finished.

    After dependencies have finished, connect a selection of their
    outpus as inputs to the dependent workchain. All the provenance
    tracking happens through links between output and input data.
    The inputs to this workchain are not stored, as it's sole purpose
    is scheduling.

    Inputs which are already available can be passed by uuid in a
    separate input.

    All input verification is up to the dependent workchain.

    Inputs:
    -------
    dependent [str]: entry point string of the dependent workchain
    dependencies [dict]: dictionary of the format
        {
            <uuid of dependency>: {
                <output name from dependency>: <input name to dependent>
            }
        }
    passthrough_inputs [dict]: dictionary of the format
        {
            <input name to the dependent>: <uuid of input node>
        }
    """

    @classmethod
    def define(cls: type, spec: workchain.WorkChainSpec) -> None:
        super().define(spec)
        spec.input("dependent", required=True, valid_type=str, non_db=True)
        spec.input("dependencies", required=True, valid_type=dict, non_db=True)
        spec.output("dependent_id")
        spec.input(
            "passthrough_inputs",
            required=False,
            valid_type=dict,
            default=lambda: {},
            non_db=True,
        )
        spec.exit_code(400, "DEPENDENCY_FAILED")
        spec.outline(
            cls.prepare,
            engine.while_(cls.is_waiting)(
                cls.await_dependencies, cls.resolve_dependencies
            ),
            cls.collected_inputs,
            cls.start_dependent,
        )

    def prepare(self) -> None:
        """Prepare the context variables."""
        self.ctx.dependency_queue = list(self.inputs.dependencies.keys())
        dep_pks = [
            orm.load_node(uuid=dep_id).pk for dep_id in self.ctx.dependency_queue
        ]
        self._report(f"Initialize dependencies as {dep_pks}.")
        self.ctx.dependency_resolution = {
            i: i for i in self.dependency_queue.wait_for_ids
        }
        self.ctx.collected_workchains = []
        self.ctx.collected_inputs = {}
        self.ctx.future_queue = []

    def _report(self, message: str) -> None:
        self.report(f"[{self.inputs.dependent}]: {message}.")

    def is_waiting(self) -> bool:
        """
        Continue to wait for dependencies until none are left.

        No futures are being awaited and none have been put in the queue
        in the last round.
        """
        return self.ctx.dependency_queue or self.ctx.future_queue

    def await_dependencies(self) -> None:
        """Load dependency nodes and start awaiting them."""
        for dependency_uuid in self.ctx.dependency_queue:
            future = orm.load_node(uuid=dependency_uuid)
            self.to_context(future_queue=engine.append_(future))
            self.ctx.dependency_queue.remove(dependency_uuid)
            self._report(f"Awaiting {future.pk}.")

    def resolve_dependencies(self) -> None:
        """Make sure to resolve any nested dependencies."""
        for future in self.ctx.future_queue:
            self._report(f"Check and resolve {future.pk}.")
            if not future.is_finished_ok:
                self._report(
                    f"Dependency {future.pk} did not finish successfully, abort."
                )
                return self.exit_codes.DEPENDENCY_FAILED
            self.ctx.future_queue.remove(future)
            if future.process_class is self.__class__:
                dependent = get_dependent(future)
                self.ctx.dependency_queue.append(dependent.uuid)
                self.ctx.dependency_resolution[
                    dependent.uuid
                ] = self.ctx.dependency_resolution[future.uuid]
                self._report(
                    f"Dependency {future.pk} is a Dependencies workflow, "
                    f"add it's dependent {dependent.pk} to dependencies"
                )
            else:
                self.ctx.collected_workchains.append(future.uuid)

    def collect_inputs(self) -> None:
        """
        After all dependencies have finished, collect dependent's inputs.
        """
        for dependency_uuid in self.ctx.collected_workchains:
            dependency = orm.load_node(uuid=dependency_uuid)
            connection_table = self.inputs.dependencies[
                self.ctx.dependency_resolution[dependency.uuid]
            ]
            self.ctx.collect_inputs |= {
                v: getattr(dependency.outputs, k) for k, v in connection_table.items()
            }
        if "passthrough_inputs" in self.inputs:
            self.ctx.collect_inputs |= {
                k: orm.load_node(uuid=v)
                for k, v in self.inputs.passthrough_inputs.items()
            }
        self._report("Collected inputs: {self.ctx.collect_inputs}.")

    def start_dependent(self) -> None:
        dependent = self.submit(
            plugins.WorkFlowFactory(self.inputs.dependent),
            **self.ctx.collected_inputs,
        )
        self._report("Start depdendent {self.inputs.dependent}: {dependent.pk}")
        self.out("dependent_id", orm.Str(dependent.uuid).store())


def get_dependent(workchain: orm.WorkChainNode) -> orm.WorkChainNode:
    return orm.load_node(workchain.outputs.dependent_id.value)
