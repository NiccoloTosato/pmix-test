import os
import reframe as rfm
import reframe.utility.typecheck as typ
import reframe.utility.sanity as sn

from prrte_build_class import build_prrte
from pmix_build_class import build_pmix
from libevent_build_class import build_libevent

class fetch_pmixtest(rfm.RunOnlyRegressionTest):
    descr = "Fetch pmix test"
    repository = f"https://github.com/openpmix/pmix-tests.git"
    executable = 'git'
    executable_opts = ["clone",f"{repository}"]
    @sanity_function
    def validate_download(self):
        return sn.assert_eq(self.job.exitcode,0)
    
    
class base_test(rfm.RunOnlyRegressionTest):
    valid_systems = ['*']
    valid_prog_environs = ['*']
    prrte = fixture(build_prrte, scope = 'environment')
    pmix =  fixture(build_pmix, scope = 'environment')
    libevent = fixture(build_libevent, scope = 'environment')
    pmix_tests = fixture(fetch_pmixtest, scope = 'session')
    path = list()
    ld_library_path = list()
    
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
    def dummy(self):
        return sn.assert_eq(self.job.exitcode,0)

@rfm.simple_test
class hello_test(base_test):
    descr = "Test if it works"
    executable = "./run.sh"
    test_name = "hello_world"
    @run_before("run")
    def compile_test(self):
        test_dir_base = self.pmix_tests.stagedir
        test_path = os.path.join(test_dir_base, "pmix-tests/prrte", self.test_name)
        print(test_path)
        self.prerun_cmds = [ f'cd {test_path}', './build.sh' ]    

@rfm.simple_test
class cycle_test(base_test):
    descr = "Test Cycle in pmix-test"
    executable = "./run.sh"
    test_name = "cycle"
    @run_before("run")
    def compile_test(self):
        test_dir_base = self.pmix_tests.stagedir
        test_path = os.path.join(test_dir_base, "pmix-tests/prrte", self.test_name)
        print(test_path)
        self.prerun_cmds = [ f'cd {test_path}', './build.sh' ]    

@rfm.simple_test
class prun_wrapper_test(base_test):
    descr = "Test prun-wrapper in pmix-test"
    executable = "./run.sh"
    test_name = "prun-wrapper"
    @run_before("run")
    def compile_test(self):
        test_dir_base = self.pmix_tests.stagedir
        test_path = os.path.join(test_dir_base, "pmix-tests/prrte", self.test_name)
        print(test_path)
        self.prerun_cmds = [ f'cd {test_path}', './build.sh' ]    

    
