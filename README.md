[![Project generated with PyScaffold](https://img.shields.io/badge/-PyScaffold-005CA0?logo=pyscaffold)](https://pyscaffold.org/)

# aiida-c2sm

> Proof-of-Concept for an ICON-CLM workflow using AiiDA.

This is a proof of concept porting part of the GCM2Icon workflow from [SPICE](https://clm-docs.scrollhelp.site/spice-doc/scripts-and-job-flow) to [AiiDA](https://www.aiida.net/).

There is [an example for running the workflow](examples/gcm2icon_submit.ipynb) for running GCM2Icon, which requires the following:

- A working installation and profile of [AiiDA](https://aiida.readthedocs.io/projects/aiida-core/en/latest/intro/get_started.html).
- This plugin installed.
- IPython installed.
- A [computer](https://aiida.readthedocs.io/projects/aiida-core/en/latest/howto/run_codes.html#how-to-run-codes) (SLURM cluster to which you can authenticate through AiiDA). The example assumes it to be named "Daint", but this can be changed easily.
- A SPICE GCM2Icon workflow set up at a specific path on the computer
- Certain data files at a specific path on the computer
- All the paths can be changed without touching the source code, but this might not be obvious how to do.


## Install

After installing `AiiDA`, preferrably in a container or virtualenv, run `pip install .` (or `pip install -e .` for development) in the same python environment.

## Further reading

AiiDA topics not covered in the given examples:

- running shell commands (not scripts): https://aiida-shell.readthedocs.io/en/latest/
- proper [testing of plugins](https://aiida.readthedocs.io/projects/aiida-core/en/latest/howto/plugins_develop.html?highlight=testing#testing-a-plugin-package) (with database isolation and mocked clusters etc)
- deleting data from intermediary steps to avoid filling up scratch quota (compare [`verdi calcjob cleanworkdir` command](https://aiida.readthedocs.io/projects/aiida-core/en/latest/reference/command_line.html?highlight=cleanworkdir#verdi-calcjob))
- [error recovery in workflows](https://aiida.readthedocs.io/projects/aiida-core/en/latest/howto/workchains_restart.html?highlight=document%20workflows)
- building higher level APIs for customizing workflows. The above mentioned `aiida-shell` plugin is an example for one way of doing that.
- improving data [queries](https://aiida.readthedocs.io/projects/aiida-core/en/latest/howto/query.html) with [extras](https://aiida.readthedocs.io/projects/aiida-core/en/latest/howto/run_codes.html?highlight=extras#managing-codes) (the example is for `Code`s but works for all data types), user defined database node metadata.

## Note

This project has been set up using PyScaffold 4.2.1. For details and
usage information on PyScaffold see <https://pyscaffold.org/>.
