import os
import reframe as rfm
import reframe.utility.typecheck as typ
import reframe.utility.sanity as sn

class fetch_libevent(rfm.RunOnlyRegressionTest):
    descr = "Fetch libevent"
    version = variable(str,value = '2.1.12')
    url = f"https://github.com/libevent/libevent/releases/download/release-{version}-stable/libevent-{version}-stable.tar.gz"
    executable = 'wget'
    executable_opts = [f"{url}"]
                       
    @sanity_function
    def validate_download(self):
        return sn.assert_eq(self.job.exitcode,0)

class build_libevent(rfm.CompileOnlyRegressionTest):
    descr = 'Build libevent'
    build_system = 'Autotools'
    build_prefix = variable(str)
    libevent = fixture(fetch_libevent, scope='session')

    @run_before('compile')
    def prepare_build(self):
        self.build_system.config_opts = [f"--prefix={self.stagedir}"]
        tarball = f"libevent-{self.libevent.version}-stable.tar.gz"
        self.build_prefix = ".".join(tarball.split(".")[:3])
        fullpath = os.path.join(self.libevent.stagedir, tarball)
        self.prebuild_cmds = [
            f'cp {fullpath} {self.stagedir}',
            f'tar xzf {tarball}',
            f'cd {self.build_prefix}'
        ]
        self.build_system.max_concurrency = 8
        self.postbuild_cmds = ['make install']
    

