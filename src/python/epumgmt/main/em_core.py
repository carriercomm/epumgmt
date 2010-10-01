import string
import sys
import time

from epumgmt.api.exceptions import *
from epumgmt.main import get_class_by_keyword, get_all_configs
from epumgmt.main import Modules, ACTIONS
import epumgmt.main.em_args as em_args
import em_core_creation
import em_core_eventgather
import em_core_fetchkill
import em_core_findworkers
import em_core_logfetch
import em_core_persistence
import em_core_status
import em_core_termination

# -----------------------------------------------------------------------------
# CORE LOGIC (this is the whole program)
# -----------------------------------------------------------------------------

def core(opts, dbgmsgs=None):
    """Run epumgmt.
    
    From here 'down' there is no concept of a commandline program, only
    'args' which could be coming from any kind of protocol based request.
    
    To make such a thing, construct an opts object with the expected
    member names and values and pass it in to this method.
    
    See the 'em_args' module and the defaults 'Parameters' implementations to
    fully understand arg intake.  See the 'em_cmdline' module to see how args
    are taken in and how the result of the program (no exception or exception)
    is translated into a return code.
    """
    
    # -------------------------------------------------------------------------
    # SETUP Parameters
    # -------------------------------------------------------------------------
    
    if not opts:
        raise InvalidInput("No arguments")
        
    # in the default deployment, this is added by the .sh script wrapper 
    if not opts.conf:
        raise InvalidInput("The path to the 'main.conf' file is required, see --help.")
        
    ac = get_all_configs(opts.conf)
    
    p_cls = get_class_by_keyword("Parameters", allconfigs=ac)
    p = p_cls(ac, opts)

    # -------------------------------------------------------------------------
    # REQUIRED arguments
    # -------------------------------------------------------------------------
    
    # --conf is also required; already checked for above
    
    given_action = p.get_arg_or_none(em_args.ACTION)
    if not given_action:
        msg = "The %s argument is required, see -h" % em_args.ACTION.long_syntax
        raise InvalidInput(msg)
        
    action = validate_action(given_action)

    # -------------------------------------------------------------------------
    # Common
    # -------------------------------------------------------------------------
    
    c_cls = get_class_by_keyword("Common", allconfigs=ac)
    c = c_cls(p)
    
    # now there is a logger finally:
    if dbgmsgs:
        c.log.debug(dbgmsgs)
        
    try:
        _core(action, p, c)
    except Exception,e:
        #c.log.exception(e)
        raise
        
def _core(action, p, c):
        
    # -------------------------------------------------------------------------
    # INSTANTIATE the rest of the needed instances
    # -------------------------------------------------------------------------
    
    event_gather_cls = c.get_class_by_keyword("EventGather")
    event_gather = event_gather_cls(p, c)
    
    iaas_cls = c.get_class_by_keyword("IaaS")
    iaas = iaas_cls(p, c)
    
    persistence = em_core_persistence.Persistence(p, c)
    
    runlogs_cls = c.get_class_by_keyword("Runlogs")
    runlogs = runlogs_cls(p, c)
    
    services_cls = c.get_class_by_keyword("Services")
    services = services_cls(p, c)
    
    # The following classes are not used in this method, this is to ensure
    # ahead of time that an implementation is configured for each object.
    #c.get_class_by_keyword("DNS")
    
    
    # -------------------------------------------------------------------------
    # VALIDATE
    # -------------------------------------------------------------------------
    
    # At least currently, this is required for all actions.
    run_name = p.get_arg_or_none(em_args.NAME)
    if not run_name:
        raise InvalidInput("The %s action requires run_name, see -h" % action)
    
    c.log.info("Validating '%s' action for '%s'" % (action, run_name))
    
    event_gather.validate()
    iaas.validate()
    persistence.validate()
    runlogs.validate()
    services.validate()
    
    modules = Modules(event_gather, iaas, persistence, runlogs, services)
    
    # -------------------------------------------------------------------------
    # BRANCH on action
    # -------------------------------------------------------------------------
    
    if c.dryrun:
        c.log.info("Performing DRYRUN '%s' for '%s'" % (action, run_name))
    else:
        c.log.info("Performing '%s' for '%s'" % (action, run_name))
    
    if action == ACTIONS.CREATE:
        em_core_creation.create(p, c, modules, run_name)
    elif action == ACTIONS.UPDATE_EVENTS:
        em_core_eventgather.update_events(p, c, modules, run_name)
    elif action == ACTIONS.KILLRUN:
        try:
            em_core_findworkers.find(p, c, modules, action, run_name, once=True)
            em_core_logfetch.fetch_all(p, c, modules, run_name)
        except KeyboardInterrupt:
            raise
        except:
            c.log.exception("Fetch failed, moving on to terminate anyhow")
        em_core_termination.terminate(p, c, modules, run_name)
    elif action == ACTIONS.FETCH_KILL:
        em_core_findworkers.find(p, c, modules, action, run_name, once=True)
        em_core_fetchkill.fetch_kill(p, c, modules, run_name)
    elif action == ACTIONS.LOGFETCH:
        em_core_logfetch.fetch_all(p, c, modules, run_name)
    elif action == ACTIONS.FIND_WORKERS:
        em_core_findworkers.find(p, c, modules, action, run_name)
    elif action == ACTIONS.FIND_WORKERS_ONCE:
        em_core_findworkers.find(p, c, modules, action, run_name, once=True)
    elif action == ACTIONS.STATUS:
        em_core_status.status(p, c, modules, run_name)
    else:
        raise ProgrammingError("unhandled action %s" % action)


# -----------------------------------------------------------------------------
# GLOBAL VALIDATIONS
# -----------------------------------------------------------------------------

def validate_action(action):
    action = string.strip(action)
    action = string.lower(action)
    if not action:
        raise InvalidInput("action is missing/empty")
                          
    if action not in ACTIONS().all_actions():
        raise InvalidInput("Unknown action: '%s'" % action)
        
    return action
