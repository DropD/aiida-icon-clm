import time

from aiida import engine, orm, plugins
from aiida.engine.processes.workchains import workchain


@engine.calcfunction
def initial_dependency_uuid() -> orm.Str:
    return orm.Str("None")


@engine.calcfunction
def one() -> orm.Int:
    return orm.Int(1)


class BuyIngredients(engine.WorkChain):
    @classmethod
    def define(cls: type, spec: workchain.WorkChainSpec) -> None:
        super().define(spec)
        spec.input("money", required=True)
        spec.output("flour")
        spec.output("water")
        spec.output("salt")
        spec.outline(cls.buy_ingredients)

    def buy_ingredients(self) -> None:
        self.report("Buying flour, salt and water!")
        time.sleep(1)
        self.out("flour", one())
        self.out("water", one())
        self.out("salt", one())


class MakeDough(engine.WorkChain):
    @classmethod
    def define(cls: type, spec: workchain.WorkChainSpec) -> None:
        super().define(spec)
        spec.input("flour")
        spec.input("water")
        spec.input("salt")
        spec.output("dough")
        spec.outline(cls.make_dough)

    def make_dough(self) -> None:
        self.report("Mixing ingredients!")
        time.sleep(1)
        self.report("Letting the dough rise!")
        time.sleep(1)
        self.report("Kneading the dough!")
        time.sleep(1)
        self.report("Letting the dough rise!")
        time.sleep(1)
        self.out("dough", one())


class PreHeatOven(engine.WorkChain):
    @classmethod
    def define(cls: type, spec: workchain.WorkChainSpec) -> None:
        super().define(spec)
        spec.input("oven_cold")
        spec.output("oven_hot")
        spec.outline(cls.heat_oven)

    def heat_oven(self) -> None:
        self.report("Heating the oven!")
        time.sleep(1)
        self.out("oven_hot", orm.Int(180).store())


class BakeBread(engine.WorkChain):
    @classmethod
    def define(cls: type, spec: workchain.WorkChainSpec) -> None:
        super().define(spec)
        spec.input("oven_clean")
        spec.input("oven_hot")
        spec.input("dough")
        spec.output("oven_dirty")
        spec.output("bread")
        spec.outline(cls.bake)

    def bake(self) -> None:
        self.report("Baking the bread!")
        time.sleep(1)
        self.out("oven_dirty", one())
        self.out("bread", one())


class SellBread(engine.WorkChain):
    @classmethod
    def define(cls: type, spec: workchain.WorkChainSpec) -> None:
        super().define(spec)
        spec.input("bread")
        spec.output("money")
        spec.outline(cls.sell)

    def sell(self) -> None:
        self.report("Selling bread for money!")
        time.sleep(1)
        self.out("money", one())


class CleanOven(engine.WorkChain):
    @classmethod
    def define(cls: type, spec: workchain.WorkChainSpec) -> None:
        super().define(spec)
        spec.input("oven_dirty")
        spec.input("oven_hot")
        spec.output("oven_clean")
        spec.output("oven_cold")
        spec.outline(cls.clean_oven)

    def clean_oven(self) -> None:
        self.report("Cleaning the oven!")
        time.sleep(1)
        self.out("oven_cold", one())
        self.out("oven_clean", one())


class BuyIngredientsFromIncome(engine.WorkChain):
    @classmethod
    def define(cls: type, spec: workchain.WorkChainSpec) -> None:
        super().define(spec)
        spec.input("sell_bread_id")
        spec.expose_outputs(BuyIngredients)
        spec.outline(cls.await_selling, cls.do_buying, cls.finalize)

    def await_selling(self) -> None:
        self.to_context(
            sell_bread=orm.WorkChainNode.objects.get(
                uuid=self.inputs.sell_bread_id.value
            )
        )

    def do_buying(self) -> None:
        self.to_context(
            ingredients=self.submit(
                BuyIngredients, money=self.ctx.sell_bread.outputs.money
            )
        )

    def finalize(self) -> None:
        self.out_many(
            self.exposed_outputs(
                self.ctx.ingredients, BuyIngredients, agglomerate=False
            )
        )


class PreHeatOvenFromCleanOven(engine.WorkChain):
    @classmethod
    def define(cls: type, spec: workchain.WorkChainSpec) -> None:
        super().define(spec)
        spec.input("clean_oven_id")
        spec.expose_outputs(PreHeatOven)
        spec.outline(cls.await_cleaning, cls.do_heating, cls.finalize)

    def await_cleaning(self) -> None:
        self.to_context(
            cleaning=orm.WorkChainNode.objects.get(uuid=self.inputs.clean_oven_id.value)
        )

    def do_heating(self) -> None:
        self.to_context(
            heat=self.submit(PreHeatOven, oven_cold=self.ctx.cleaning.outputs.oven_cold)
        )

    def finalize(self) -> None:
        self.out_many(
            self.exposed_outputs(self.ctx.heat, PreHeatOven, agglomerate=False)
        )


class BakeryIteration(engine.WorkChain):
    @classmethod
    def define(cls: type, spec: workchain.WorkChainSpec) -> None:
        super().define(spec)
        spec.input("iteration_nr")
        spec.input("capital_provider", required=False, default=initial_dependency_uuid)
        spec.input("cleaning_provider", required=False, default=initial_dependency_uuid)
        spec.output("clean_oven_id")
        spec.output("sell_bread_id")
        spec.outline(
            cls.buy_ingredients,
            cls.pre_heat_oven,
            cls.wait_for_ingredients,
            cls.make_dough,
            cls.wait_for_hot_oven,
            cls.bake_bread,
            cls.sell_bread,
            cls.clean_oven,
        )

    def buy_ingredients(self) -> None:
        if self.inputs.iteration_nr.value <= 2:
            ingredients = self.submit(BuyIngredients, money=one())
            self.ctx.ingredients_id = ingredients.uuid
        else:
            ingredients = self.submit(
                BuyIngredientsFromIncome,
                sell_bread_id=self.inputs.capital_provider,
            )
            self.ctx.ingredients_id = ingredients.uuid

    def pre_heat_oven(self) -> None:
        if self.inputs.iteration_nr.value <= 1:
            hot_oven = self.submit(PreHeatOven, oven_cold=one())
            self.ctx.hot_oven_id = hot_oven.uuid
        else:
            hot_oven = self.submit(
                PreHeatOvenFromCleanOven,
                clean_oven_id=self.inputs.cleaning_provider,
            )
            self.ctx.hot_oven_id = hot_oven.uuid

    def wait_for_ingredients(self) -> None:
        self.to_context(
            ingredients=orm.WorkChainNode.objects.get(uuid=self.ctx.ingredients_id)
        )

    def make_dough(self) -> None:
        dough = self.submit(
            MakeDough,
            flour=self.ctx.ingredients.outputs.flour,
            water=self.ctx.ingredients.outputs.water,
            salt=self.ctx.ingredients.outputs.salt,
        )
        self.to_context(dough=dough)

    def wait_for_hot_oven(self) -> None:
        self.to_context(
            hot_oven=orm.WorkChainNode.objects.get(uuid=self.ctx.hot_oven_id)
        )

    def bake_bread(self) -> None:
        bread = self.submit(
            BakeBread,
            dough=self.ctx.dough.outputs.dough,
            oven_clean=one(),
            oven_hot=self.ctx.hot_oven.outputs.oven_hot,
        )
        self.to_context(bread=bread)

    def sell_bread(self) -> None:
        sold = self.submit(SellBread, bread=self.ctx.bread.outputs.bread)
        self.out("sell_bread_id", orm.Str(sold.uuid).store())

    def clean_oven(self) -> None:
        cleaned = self.submit(
            CleanOven,
            oven_dirty=self.ctx.bread.outputs.oven_dirty,
            oven_hot=self.ctx.hot_oven.outputs.oven_hot,
        )
        self.out("clean_oven_id", orm.Str(cleaned.uuid).store())


class WaitForDependencies(engine.WorkChain):
    @classmethod
    def define(cls: type, spec: workchain.WorkChainSpec) -> None:
        """
        Start `dependent` with outpus from `dependencies` as inputs.

        Inputs:
        -------

        - dependent: [Str], entry point for the dependent workchain type.
        - dependencies: [Dict], uuid of running or finished dependency workchains.
            {"uuid": {"output_name": "input_name"}, [...]}
        """
        super().define(spec)
        spec.input("dependent", required=True, valid_type=orm.Str)
        spec.input("dependencies", required=True, valid_type=orm.Dict)
        spec.input("passthrough_inputs", required=False, valid_type=orm.Dict)
        spec.output("dependent_id")
        spec.outline(
            cls.prepare,
            engine.while_(cls.dependencies_left)(cls.push_futures, cls.collect_inputs),
            cls.start_dependent,
        )

    def prepare(self) -> None:
        self.ctx.wait_for_ids = list(self.inputs.dependencies.keys())
        self.report(
            f"Wait({self.inputs.dependent.value}): initial dependencies {self.ctx.wait_for_ids}"
        )
        self.ctx.dependent_inputs = {}
        self.ctx.resolution_table = {i: i for i in self.ctx.wait_for_ids}
        self.ctx.futures = []

    def dependencies_left(self) -> bool:
        return bool(self.ctx.wait_for_ids) or bool(self.ctx.futures)

    def push_futures(self) -> None:
        for dependency_id in self.ctx.wait_for_ids:
            self.report(f"Wait({self.inputs.dependent.value}): pushing {dependency_id}")
            self.to_context(
                futures=engine.append_(
                    orm.WorkChainNode.collection.get(uuid=dependency_id)
                )
            )
            self.ctx.wait_for_ids.remove(dependency_id)

    def collect_inputs(self) -> None:
        for dependency in self.ctx.futures:
            self.report(
                f"Wait({self.inputs.dependent.value}): checking on {dependency}"
            )
            assert dependency.is_finished_ok
            if dependency.process_class is self.__class__:
                dependent_id = dependency.outputs.dependent_id.value
                self.ctx.wait_for_ids.append(dependent_id)
                self.ctx.resolution_table[dependent_id] = self.ctx.resolution_table[
                    dependency.uuid
                ]
                self.report(
                    f"Wait({self.inputs.dependent.value}): -> it's a waiter, waiting for it's "
                    f"dependent {dependent_id}"
                )
            else:
                self.ctx.dependent_inputs.update(
                    {
                        v: getattr(dependency.outputs, k)
                        for k, v in self.inputs.dependencies[
                            self.ctx.resolution_table[dependency.uuid]
                        ].items()
                    }
                )
            self.ctx.futures.remove(dependency)

        self.report(
            f"Wait({self.inputs.dependent.value}): collected {self.ctx.dependent_inputs}"
        )

    def start_dependent(self) -> None:
        if "passthrough_inputs" in self.inputs:
            self.ctx.dependent_inputs |= {
                k: orm.load_node(uuid=v)
                for k, v in self.inputs.passthrough_inputs.items()
            }

        self.report(
            f"Wait({self.inputs.dependent.value}): start baking with {self.ctx.dependent_inputs}"
        )
        dependent = self.submit(
            plugins.WorkflowFactory(self.inputs.dependent.value),
            **self.ctx.dependent_inputs,
        )
        self.out("dependent_id", orm.Str(dependent.uuid).store())


class BakeryCycle(engine.WorkChain):
    @classmethod
    def define(cls: type, spec: workchain.WorkChainSpec) -> None:
        super().define(spec)
        spec.input("start_iteration", required=True, valid_type=orm.Int)
        spec.input("end_iteration", required=True, valid_type=orm.Int)
        spec.outline(
            cls.prepare,
            engine.while_(cls.should_continue)(
                cls.run_iteration, cls.increment_iteration
            ),
        )

    def prepare(self) -> None:
        self.report("Preparing")
        self.ctx.iteration_nr = self.inputs.start_iteration.value
        self.ctx.ingredients_ids = []
        self.ctx.clean_oven_ids = []
        self.ctx.sell_bread_ids = []
        self.ctx.seed_money = one()
        self.ctx.oven_cold_start = one()
        self.ctx.oven_clean_start = one()
        self.ctx.buy_ingredients_str = orm.Str("c2sm.bakery_buy_ingredients").store()
        self.ctx.pre_heat_str = orm.Str("c2sm.bakery_pre_heat_oven").store()
        self.ctx.make_dough_str = orm.Str("c2sm.bakery_make_dough").store()
        self.ctx.bake_bread_str = orm.Str("c2sm.bakery_bake_bread").store()
        self.ctx.clean_oven_str = orm.Str("c2sm.bakery_clean_oven").store()
        self.ctx.sell_bread_str = orm.Str("c2sm.bakery_sell_bread").store()
        self.ctx.empty_dependencies = orm.Dict().store()

    def should_continue(self) -> bool:
        return bool(self.ctx.iteration_nr <= self.inputs.end_iteration)

    def run_iteration(self) -> None:
        self.report("Buying ingredients!")
        if self.ctx.iteration_nr <= 2:
            self.ctx.ingredients_ids.append(
                self.submit(BuyIngredients, money=self.ctx.seed_money).uuid
            )
        else:
            self.ctx.ingredients_ids.append(
                self.submit(
                    WaitForDependencies,
                    dependent=self.ctx.buy_ingredients_str,
                    dependencies=orm.Dict(
                        {self.ctx.sell_bread_ids[-2]: {"money": "money"}}
                    ).store(),
                ).uuid
            )

        self.report("Heating oven!")
        hot_oven = None
        if self.ctx.iteration_nr <= 1:
            hot_oven = self.submit(PreHeatOven, oven_cold=self.ctx.oven_cold_start)
        else:
            hot_oven = self.submit(
                WaitForDependencies,
                dependent=self.ctx.pre_heat_str,
                dependencies=orm.Dict(
                    {self.ctx.clean_oven_ids[-1]: {"oven_cold": "oven_cold"}}
                ),
            )

        self.report("Making dough!")
        bake_bread_dependencies = {
            self.ctx.ingredients_ids[-1]: {
                "flour": "flour",
                "water": "water",
                "salt": "salt",
            },
        }
        make_dough = self.submit(
            WaitForDependencies,
            dependent=self.ctx.make_dough_str,
            dependencies=orm.Dict(bake_bread_dependencies).store(),
        )

        self.report("Baking bread!")
        bake_bread_dependencies = {
            hot_oven.uuid: {"oven_hot": "oven_hot"},
            make_dough.uuid: {"dough": "dough"},
        }
        passthrough_inputs = {}
        if (
            self.ctx.iteration_nr > 1
        ):  # TODO: starting at iteration number > 1 would break
            bake_bread_dependencies |= {
                self.ctx.clean_oven_ids[-1]: {"oven_clean": "oven_clean"}
            }
        else:
            passthrough_inputs = {
                "passthrough_inputs": orm.Dict(
                    {"oven_clean": self.ctx.oven_clean_start.uuid}
                ).store()
            }
        bake_bread = self.submit(
            WaitForDependencies,
            dependent=self.ctx.bake_bread_str,
            dependencies=orm.Dict(bake_bread_dependencies).store(),
            **passthrough_inputs,
        )

        self.report("Cleaning oven!")
        self.ctx.clean_oven_ids.append(
            self.submit(
                WaitForDependencies,
                dependent=self.ctx.clean_oven_str,
                dependencies=orm.Dict(
                    {
                        hot_oven.uuid: {"oven_hot": "oven_hot"},
                        bake_bread.uuid: {"oven_dirty": "oven_dirty"},
                    }
                ).store(),
            ).uuid
        )

        self.report("Selling bread!")
        self.ctx.sell_bread_ids.append(
            self.submit(
                WaitForDependencies,
                dependent=self.ctx.sell_bread_str,
                dependencies=orm.Dict({bake_bread.uuid: {"bread": "bread"}}).store(),
            ).uuid
        )

        self.to_context(latest_baked_bread=bake_bread)

    def increment_iteration(self) -> None:
        self.report("Waiting for baked bread!")
        self.ctx.latest_baked_bread.is_finished_ok
        self.ctx.iteration_nr += 1
