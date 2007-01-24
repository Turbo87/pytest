
""" reporter - different reporter for different purposes ;-)
    Still lacks:
    
    1. Hanging nodes are not good done
"""

import py

from py.__.test.terminal.out import getout
from py.__.test.rsession import report
from py.__.test.rsession import outcome

class AbstractReporter(object):
    def __init__(self, config, hosts, pkgdir=py.path.local(py.__file__)):
        self.config = config
        self.pkgdir = pkgdir
        self.hosts = hosts
        self.failed_tests_outcome = []
        self.skipped_tests_outcome = []
        self.out = getout(py.std.sys.stdout)
        self.failed = dict([(host, 0) for host in hosts])
        self.skipped = dict([(host, 0) for host in hosts])
        self.passed = dict([(host, 0) for host in hosts])

    def get_item_name(self, event, colitem):
        return "/".join(colitem.listnames())
    
    def report(self, what):
        repfun = getattr(self, "report_" + what.__class__.__name__, 
                         self.report_unknown)
        try:
            return repfun(what)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            print "Internal reporting problem"
            excinfo = py.code.ExceptionInfo()
            for i in excinfo.traceback:
                print str(i)[2:-1]
            print excinfo
    
    def report_unknown(self, what):
        if self.config.option.verbose: 
            print "Unknown report: %s" % what
    
    def report_SendItem(self, item):
        address = item.host.hostname
        if self.config.option.verbose: 
            print "Sending %s to %s" % (item.item,
                                        address)
    
    def report_HostRSyncing(self, item):
        print "%10s: RSYNC ==> %s" % (item.host.hostname[:10],
                                      item.host.relpath)
    
    def report_HostReady(self, item):
        self.hosts_to_rsync -= 1
        if self.hosts_to_rsync:
            print "%10s: READY (still %d to go)" % (item.host.hostname[:10],
                                                self.hosts_to_rsync)
        else:
            print "%10s: READY" % item.host.hostname[:10]
    
    def report_TestStarted(self, item):
        hostnames = [host.hostname for host in item.hosts]
        txt = " Test started, hosts: %s " % ", ".join(hostnames)
        self.hosts_to_rsync = len(item.hosts)
        self.out.sep("=", txt)
        self.timestart = item.timestart

    def report_RsyncFinished(self, item):
        self.timersync = item.time
    
    def report_ImmediateFailure(self, event):
        self.repr_failure(event.item, event.outcome)
    
    def report_TestFinished(self, item):
        self.out.line()
        assert hasattr(self, 'timestart')
        self.timeend = item.timeend
        self.skips()
        self.failures()
        if hasattr(self, 'nodes'): # XXX: Testing
            self.hangs()
        self.summary()
        return len(self.failed_tests_outcome) > 0
    
    def hangs(self):
        h = []
        if self.config.option.exitfirst:
            # reporting hanging nodes in that case makes no sense at all
            # but we should share some code in all reporters than
            return
        for node in self.nodes:
            h += [(i, node.channel.gateway.sshaddress) for i in node.pending]
        if h:
            self.out.sep("=", " HANGING NODES ")
            for i, node in h:
                self.out.line("%s on %s" % (" ".join(i.listnames()), node))
    
    def failures(self):
        if self.failed_tests_outcome:
            self.out.sep("=", " FAILURES ")
        for event in self.failed_tests_outcome:
            if isinstance(event, report.ReceivedItemOutcome):
                host = self.gethost(event)
                self.out.sep('_', "%s on %s" % 
                    (" ".join(event.item.listnames()), host))
                if event.outcome.signal:
                    self.repr_signal(event.item, event.outcome)
                else:
                    self.repr_failure(event.item, event.outcome)
            else:
                self.out.sep('_', " ".join(event.item.listnames()))
                out = outcome.Outcome(excinfo=event.excinfo)
                self.repr_failure(event.item, outcome.ReprOutcome(out.make_repr()))

    def gethost(self, event):
        return event.host.hostname
    
    def repr_failure(self, item, outcome): 
        excinfo = outcome.excinfo
        traceback = excinfo.traceback
        #if item and not self.config.option.fulltrace: 
        #    path, firstlineno = item.getpathlineno()
        if not traceback: 
            self.out.line("empty traceback from item %r" % (item,)) 
            return
        #handler = getattr(self, 'repr_failure_tb%s' % self.config.option.tbstyle)
        self.repr_traceback(item, excinfo, traceback)
        if outcome.stdout:
            self.out.sep('-', " Captured process stdout: ")
            self.out.write(outcome.stdout)
        if outcome.stderr:
            self.out.sep('-', " Captured process stderr: ")
            self.out.write(outcome.stderr)
    
    def repr_signal(self, item, outcome):
        signal = outcome.signal
        self.out.line("Received signal: %d" % outcome.signal)
        if outcome.stdout:
            self.out.sep('-', " Captured process stdout: ")
            self.out.write(outcome.stdout)
        if outcome.stderr:
            self.out.sep('-', " Captured process stderr: ")
            self.out.write(outcome.stderr)

    def repr_traceback(self, item, excinfo, traceback):
        if self.config.option.tbstyle == 'long':
            for index, entry in py.builtin.enumerate(traceback): 
                self.out.sep('-')
                self.out.line("%s: %s" % (entry.path, entry.lineno))
                self.repr_source(entry.relline, str(entry.source))
        elif self.config.option.tbstyle == 'short':
            for index, entry in py.builtin.enumerate(traceback): 
                self.out.line("%s: %s" % (entry.path, entry.lineno))
                self.out.line(entry.source)
        self.out.line("%s: %s" % (excinfo.typename, excinfo.value))
    
    def repr_source(self, relline, source):
        for num, line in enumerate(source.split("\n")):
            if num == relline:
                self.out.line(">>>>" + line)
            else:
                self.out.line("    " + line)
            
    def skips(self):
        texts = {}
        for event in self.skipped_tests_outcome:
            colitem = event.item
            if isinstance(event, report.ReceivedItemOutcome):
                outcome = event.outcome
                text = outcome.skipped
                itemname = self.get_item_name(event, colitem)
            elif isinstance(event, report.SkippedTryiter):
                text = str(event.excinfo.value)
                itemname = "/".join(colitem.listnames())
            if text not in texts:
                texts[text] = [itemname]
            else:
                texts[text].append(itemname)
            
        if texts:
            self.out.line()
            self.out.sep('_', 'reasons for skipped tests')
            for text, items in texts.items():
                for item in items:
                    self.out.line('Skipped in %s' % item)
                self.out.line("reason: %s" % text)
    
    def summary(self):
        def gather(dic):
            total = 0
            for key, val in dic.iteritems():
                total += val
            return total
        
        def create_str(name, count):
            if count:
                return ", %d %s" % (count, name)
            return ""

        total_passed = gather(self.passed)
        total_failed = gather(self.failed)
        total_skipped = gather(self.skipped)
        total = total_passed + total_failed + total_skipped
        skipped_str = create_str("skipped", total_skipped)
        failed_str = create_str("failed", total_failed)
        self.print_summary(total, skipped_str, failed_str)
    
    def print_summary(self, total, skipped_str, failed_str):
        self.out.sep("=", " %d test run%s%s in %.2fs (rsync: %.2f)" % 
            (total, skipped_str, failed_str, self.timeend - self.timestart,
             self.timersync - self.timestart))
    
    def report_SkippedTryiter(self, event):
        #event.outcome.excinfo.source = 
        self.skipped_tests_outcome.append(event)
    
    def report_FailedTryiter(self, event):
        pass
        # XXX: right now we do not do anything with it
    
    def report_ReceivedItemOutcome(self, event):
        host = event.host
        if event.outcome.passed:
            status = "PASSED "
            self.passed[host] += 1
        elif event.outcome.skipped:
            status = "SKIPPED"
            self.skipped_tests_outcome.append(event)
            self.skipped[host] += 1
        else:
            status = "FAILED "
            self.failed[host] += 1
            self.failed_tests_outcome.append(event)
            # we'll take care of them later
        itempath = " ".join(event.item.listnames()[1:])
        print "%10s: %s %s" %(host.hostname[:10], status, itempath)
    
    def report_Nodes(self, event):
        self.nodes = event.nodes

class RemoteReporter(AbstractReporter):    
    def get_item_name(self, event, colitem):
        return event.host.hostname + ":" + \
            "/".join(colitem.listnames())
        
    def report_FailedTryiter(self, event):
        self.out.line("FAILED TO LOAD MODULE: %s\n" % "/".join(event.item.listnames()))
        self.failed_tests_outcome.append(event)
    
    def report_SkippedTryiter(self, event):
        self.out.line("Skipped (%s) %s\n" % (str(event.excinfo.value), "/".
            join(event.item.listnames())))

class LocalReporter(AbstractReporter):
    def get_item_name(self, event, colitem):
        return "/".join(colitem.listnames())
    
    def report_SkippedTryiter(self, event):
        #self.show_item(event.item, False)
        self.out.write("- skipped (%s)" % event.excinfo.value)
    
    def report_FailedTryiter(self, event):
        #self.show_item(event.item, False)
        self.out.write("- FAILED TO LOAD MODULE")
        self.failed_tests_outcome.append(event)
    
    def report_ReceivedItemOutcome(self, event):
        host = self.hosts[0]
        if event.outcome.passed:
            self.passed[host] += 1
            self.out.write(".")
        elif event.outcome.skipped:
            self.skipped_tests_outcome.append(event)
            self.skipped[host] += 1
            self.out.write("s")
        else:
            self.failed[host] += 1
            self.failed_tests_outcome.append(event)
            self.out.write("F")
    
    def report_ItemStart(self, event):
        self.show_item(event.item)
    
    def show_item(self, item, count_elems = True):
        if isinstance(item, py.test.collect.Module):
            # XXX This is a terrible hack, I don't like it
            #     and will rewrite it at some point
            #self.count = 0
            lgt = len(list(item.tryiter()))
            #self.lgt = lgt
            # print names relative to current workdir
            name = "/".join(item.listnames())
            local = str(py.path.local())
            d = str(self.pkgdir.dirpath().dirpath())
            if local.startswith(d):
                local = local[len(d) + 1:]
            if local and name.startswith(local):
                name = name[len(local) + 1:]
            self.out.write("\n%s[%d] " % (name, lgt))

    def gethost(self, event):
        return 'localhost'
    
    def hangs(self):
        pass
