import os

from epucontrol.api.exceptions import *
import epucontrol.main.ec_args as ec_args
from epucontrol.main import ACTIONS

class DefaultRunlogs:
    
    def __init__(self, params, common):
        self.p = params
        self.c = common
        self.validated = False
        self.thisrundir = None

        # temporary assumption that this is same on every VM, see events.conf
        self.allvmslogdir = None
        
    def validate(self):
        
        action = self.p.get_arg_or_none(ec_args.ACTION)
        if action not in [ACTIONS.CREATE, ACTIONS.LOGFETCH]:
            if self.c.trace:
                self.c.log.debug("validation for runlogs module complete, '%s' is not a relevant action" % action)
            return
        
        run_name = self.p.get_arg_or_none(ec_args.NAME)
        
        runlogdir = self.p.get_conf_or_none("events", "runlogdir")
        if not runlogdir:
            raise InvalidConfig("There is no runlogdir configuration")
        
        if not os.path.isabs(runlogdir):
            runlogdir = self.c.resolve_var_dir(runlogdir)
        
        if not os.path.exists(runlogdir):
            raise InvalidConfig("The runlogdir does not exist: %s" % runlogdir)
        
        self.thisrundir = os.path.join(runlogdir, run_name)
        if not os.path.exists(self.thisrundir):
            os.mkdir(self.thisrundir)
            self.c.log.debug("Created a new directory for the logfiles generated on nodes in this run: %s" % self.thisrundir)
        else:
            self.c.log.debug("Directory of logfiles generated on nodes in this run: %s" % self.thisrundir)
        
        self.allvmslogdir = self.p.get_conf_or_none("events", "vmlogdir")
        if not self.allvmslogdir:
            raise InvalidConfig("There is no events:vmlogdir configuration")

        self.validated = True


    def new_vm(self, newvm):
        """Make the module aware of a new VM.
        It also will annotate the VM object.  It can handle a VM that has
        been through this process before, so no need to check for it.
        """
        
        if not self.validated:
            raise ProgrammingError("operation called without necessary validation")
            
        if not newvm.instanceid:
            raise ProgrammingError("Cannot determine VM instance ID")
            
        thisvm_runlog_dir = os.path.join(self.thisrundir, newvm.instanceid)
            
        if newvm.runlogdir:
            if newvm.runlogdir != thisvm_runlog_dir:
                self.c.log.warn("The runlog directory for the VM was recorded but it is not what we would expect (%s != %s)" % (newvm.runlogdir, thisvm_runlog_dir))
        else:
            os.mkdir(thisvm_runlog_dir)
            newvm.runlogdir = thisvm_runlog_dir
            self.c.log.debug("created runlog directory for this instance: %s" % thisvm_runlog_dir)
            
        if not os.path.exists(newvm.runlogdir):
            raise IncompatibleEnvironment("Could not find the runlog directory: %s" % newvm.runlogdir)
        
        newvm.vmlogdir = self.allvmslogdir
        
        
    def fetch_logs(self, vm, m):
        
        if not self.validated:
            raise ProgrammingError("operation called without necessary validation")
            
        scpcmd = m.iaas.scp_cmd(vm.hostname)
    
        # last arg is "user@host:", we need to enhance this with the path
        scpcmd[-1] = scpcmd[-1] + vm.vmlogdir
        
        # and then the glob
        scpcmd[-1] = scpcmd[-1] + "/*log"
        
        # transfer destination
        scpcmd.append(vm.runlogdir)
        
        # bad: hijacking known impl of a module
        # TODO: modules should each be entirely pluggable, that is the point
        m.iaas._one_cmd(scpcmd)
