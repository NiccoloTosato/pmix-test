import os
import time
from packaging.version import parse as parse_version

import reframe as rfm
import reframe.utility.typecheck as typ
import reframe.utility.sanity as sn


from prrte_build_class import build_prrte
from pmix_build_class import build_pmix
from libevent_build_class import build_libevent

class fetch_pmixtest(rfm.RunOnlyRegressionTest):
    descr = "Fetch pmix test"
    repository = f"https://github.com/NiccoloTosato/pmix-tests.git"
    executable = 'git'
    executable_opts = ["clone",f"{repository}"]
    local = True
    @sanity_function
    def validate_download(self):
        return sn.assert_eq(self.job.exitcode,0)

class test_builder(rfm.CompileOnlyRegressionTest):
    build_system = 'CustomBuild'
    prrte = fixture(build_prrte, scope = 'environment')
    pmix =  fixture(build_pmix, scope = 'environment')
    libevent = fixture(build_libevent, scope = 'environment')
    pmix_tests = fixture(fetch_pmixtest, scope = 'session')
    path = list()
    test_base_path=""
    ld_library_path = list()
    @run_before('compile')
    def prepare_env(self):
        for fix in [self.prrte, self.pmix, self.libevent]:
            self.path.append(os.path.join(fix.stagedir,"bin"))
            self.ld_library_path.append(os.path.join(fix.stagedir,"lib"))
        self.env_vars = {
            "PATH" : ":".join(self.path) + ":${PATH}",
            "LD_LIBRARY_PATH" : ":".join(self.ld_library_path) + ":${LD_LIBRARY_PATH}"
        }
        self.test_base_path=os.path.join(self.pmix_tests.stagedir,"pmix-tests","prrte")

class build_hello_world(test_builder):
    descr = 'Build pmix hello world test'
    test_name = "hello_world"
    @run_before('compile',always_last=True)
    def prepare_build(self):
        self.test_path = os.path.join(self.test_base_path, self.test_name)
        self.build_system.commands = [
            f'cd {self.test_path}', './build.sh'
        ]

class build_prun_wrapper(test_builder):
    descr = 'Build pmix prun-wrapper'
    test_name = "prun-wrapper"
    @run_before('compile',always_last=True)
    def prepare_build(self):
        self.test_path = os.path.join(self.test_base_path, self.test_name)
        self.build_system.commands = [
            f'cd {self.test_path}', './build.sh'
        ]

class build_cycle(test_builder):
    descr = 'Build pmix cycle'
    test_name = "cycle"
    @run_before('compile',always_last=True)
    def prepare_build(self):
        self.test_path = os.path.join(self.test_base_path, self.test_name)
        self.build_system.commands = [
            f'cd {self.test_path}', './build.sh'
        ]
    
    
class base_test(rfm.RunOnlyRegressionTest):
    valid_systems = ['*']
    valid_prog_environs = ['*']
    prrte = fixture(build_prrte, scope = 'environment')
    pmix =  fixture(build_pmix, scope = 'environment')
    libevent = fixture(build_libevent, scope = 'environment')
    pmix_tests = fixture(fetch_pmixtest, scope = 'session')
    path = list()
    ld_library_path = list()
    num_cpus_per_task = 1
    time_limit = '0d0h5m0s'
    @run_before('run')
    def prepare_run(self):
        for fix in [self.prrte, self.pmix, self.libevent]:
            self.path.append(os.path.join(fix.stagedir,"bin"))
            self.ld_library_path.append(os.path.join(fix.stagedir,"lib"))
        self.env_vars = {
            "PATH" : ":".join(self.path) + ":${PATH}",
            "LD_LIBRARY_PATH" : ":".join(self.ld_library_path) + ":${LD_LIBRARY_PATH}"
        }
        self.executable = os.path.join("")
        # prepare the environment, with LD and PATH
    @sanity_function
    def retcode(self):
        return sn.assert_eq(self.job.exitcode,0)


@rfm.simple_test
class hostname_test(base_test):
    descr = "Test pmix hostname"
    test_name = "hostname"
    num_tasks = 120
    num_tasks_per_node = 12
    hello_test = fixture(build_hello_world,scope = 'environment')

    @run_before("run")
    def prepare_test(self):
        test_path = self.hello_test.test_path
        #1. Change folder 2. Init the DVM 3. set time output to be parsable later
        self.prerun_cmds = [ f'cd {test_path}', 'prte --no-ready-msg &', 'TIMEFORMAT="runtime,%R,%U,%S"','sleep 5']
        self.executable="time"
        self.executable_opts = ["prun", f"--map-by ppr:{self.num_tasks_per_node}:node", "hostname"]
        # At the end shutdown the dvm
        self.postrun_cmds = ["pterm"]
    @performance_function('s')
    def walltime(self):
        patt = r"runtime,(\d+\.\d+),(\d+\.\d+),(\d+\.\d+)"
        # Extract the values
        return sn.extractsingle(
            patt, 
            self.stderr,          
            tag=(1),        # Capture Group 1 (Real), Group 2 (User), Group 3 (Sys), Get only 1
            conv=float            
        )
    @sanity_function
    def check_output(self):
        # Get the pattern to match the compute node
        patt = self.current_system.hostnames[0]
        line_count = sn.count(sn.extractall(patt,self.stdout,0))
        # Append to flags all the deferrend functions
        flags = list()
        # 1. Count the number of line that match hostnames
        flags.append(sn.assert_eq(line_count,self.num_tasks))
        # 2. Check if there is ERROR in the stderr, count them
        total_errors = sn.count(sn.findall(r'\bERROR\b', self.stderr))
        
        #TODO: find a smarter way to encapsulate versions !
        current_version = parse_version(self.pmix.pmix.version)
        known_broken_version = parse_version("6.1.0")
        if current_version == known_broken_version:
            # Ignore some errors from  pmix v6.1.0, we expect a race condition, see https://github.com/openpmix/prrte/issues/2431
            known_bug_pattern = r'contact information is unknown in file iof_hnp\.c at line 222'
            known_bugs = sn.count(sn.findall(known_bug_pattern, self.stderr))
            # Assert that every 'ERROR' found is accounted for by the known bug
            print(f"Bug count: {known_bugs}")
            flags.append(sn.assert_eq(total_errors, known_bugs))
        else:
            flags.append(sn.assert_eq(total_errors, 0))
        # Return the evaluation of flags! 
        return sn.all(flags)

        
@rfm.simple_test
class hello_world_test(base_test):
    descr = "Test pmix hello_world"
    test_name = "hello_world"
    num_tasks = 120
    num_tasks_per_node = 12
    hello_test = fixture(build_hello_world,scope = 'environment')
    @run_before("run")
    def prepare_test(self):
        test_path = self.hello_test.test_path
        #1. Change folder 2. Init the DVM 3. set time output to be parsable later
        self.prerun_cmds = [ f'cd {test_path}', 'prte --no-ready-msg &', 'TIMEFORMAT="runtime,%R,%U,%S"','sleep 5']
        self.executable="time"
        self.executable_opts = ["prun", f"--map-by ppr:{self.num_tasks_per_node}:node", "hostname"]
        # At the end shutdown the dvm
        self.postrun_cmds = ["pterm"]

    @performance_function('s')
    def walltime(self):
        patt = r"runtime,(\d+\.\d+),(\d+\.\d+),(\d+\.\d+)"
        # Extract the values
        return sn.extractsingle(
            patt, 
            self.stderr,          
            tag=(1),        # Capture Group 1 (Real), Group 2 (User), Group 3 (Sys), Get only 1
            conv=float            
        )

    @sanity_function
    def count_output(self):
        patt = self.current_system.hostnames[0]
        #Extract the values
        line_count = sn.count(sn.extractall(patt,self.stdout,0))
        return sn.assert_eq(line_count,self.num_tasks)


@rfm.simple_test
class cycle_test(base_test):
    descr = "Test Cycle in pmix-test"
    test_name = "cycle"
    num_tasks = 120
    num_tasks_per_node = 12
    cycle_test = fixture(build_cycle,scope = 'environment')
    @run_before("run")
    def prepare_test(self):
        test_path = self.cycle_test.test_path
        self.prerun_cmds = [ f'cd {test_path}' ]    
        self.executable="./run.sh"

@rfm.simple_test
class prun_wrapper_test(base_test):
    descr = "Test prun-wrapper in pmix-test"
    test_name = "prun-wrapper"
    num_tasks = 120
    num_tasks_per_node = 12
    prun_test = fixture(build_prun_wrapper,scope = 'environment')
    @run_before("run")
    def prepare_test(self):
        test_path = self.prun_test.test_path
        self.prerun_cmds = [ f'cd {test_path}', 'scontrol show hostnames $SLURM_JOB_NODELIST > hostfile.txt' ]    
        self.executable="./run.sh"
        self.env_vars['CI_HOSTFILE'] = f"{os.path.join(test_path,'hostfile.txt')}"
