"""Bound one owned subprocess tree; no access-policy or credential changes."""
import hashlib,os,re,signal,subprocess,tempfile,threading,time

class OwnedProcessError(RuntimeError):pass

class WindowsJob:
    def __init__(self):
        import ctypes
        from ctypes import wintypes as w
        self.c=ctypes;self.k=ctypes.WinDLL('kernel32',use_last_error=True)
        class Basic(ctypes.Structure):
            _fields_=[('process_time',ctypes.c_int64),('job_time',ctypes.c_int64),('flags',w.DWORD),
                ('min_working_set',ctypes.c_size_t),('max_working_set',ctypes.c_size_t),('active_limit',w.DWORD),
                ('affinity',ctypes.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]
        class IO(ctypes.Structure):_fields_=[(x,ctypes.c_uint64) for x in ('ro','wo','oo','rb','wb','ob')]
        class Extended(ctypes.Structure):
            _fields_=[('basic',Basic),('io',IO),('process_memory',ctypes.c_size_t),('job_memory',ctypes.c_size_t),
                     ('peak_process_memory',ctypes.c_size_t),('peak_job_memory',ctypes.c_size_t)]
        class Accounting(ctypes.Structure):
            _fields_=[('user',ctypes.c_int64),('kernel',ctypes.c_int64),('period_user',ctypes.c_int64),
                ('period_kernel',ctypes.c_int64),('faults',w.DWORD),('total',w.DWORD),
                ('active',w.DWORD),('terminated',w.DWORD)]
        self.Accounting=Accounting
        self.k.CreateJobObjectW.argtypes=[w.LPVOID,w.LPCWSTR];self.k.CreateJobObjectW.restype=w.HANDLE
        self.k.SetInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,w.LPVOID,w.DWORD];self.k.SetInformationJobObject.restype=w.BOOL
        self.k.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE];self.k.AssignProcessToJobObject.restype=w.BOOL
        self.k.CloseHandle.argtypes=[w.HANDLE];self.k.CloseHandle.restype=w.BOOL
        self.k.TerminateJobObject.argtypes=[w.HANDLE,w.UINT];self.k.TerminateJobObject.restype=w.BOOL
        self.k.QueryInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,w.LPVOID,w.DWORD,w.LPVOID]
        self.k.QueryInformationJobObject.restype=w.BOOL
        self.k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];self.k.OpenProcess.restype=w.HANDLE
        self.k.IsProcessInJob.argtypes=[w.HANDLE,w.HANDLE,ctypes.POINTER(w.BOOL)];self.k.IsProcessInJob.restype=w.BOOL
        self.k.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD];self.k.WaitForSingleObject.restype=w.DWORD
        class Pids(ctypes.Structure):
            _fields_=[('assigned',w.DWORD),('listed',w.DWORD),('ids',ctypes.c_size_t*2048)]
        self.Pids=Pids
        self.handle=self.k.CreateJobObjectW(None,None)
        if not self.handle:raise OwnedProcessError('owned_job_creation_denied')
        info=Extended();info.basic.flags=0x2000 # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.k.SetInformationJobObject(self.handle,9,ctypes.byref(info),ctypes.sizeof(info)):
            self.close();raise OwnedProcessError('owned_job_limits_denied')
    def start(self,process):
        # Popen starts suspended: no model/tool child can escape before assignment.
        if not self.k.AssignProcessToJobObject(self.handle,int(process._handle)):
            raise OwnedProcessError('owned_job_assignment_denied')
        resume=self.c.WinDLL('ntdll').NtResumeProcess
        resume.argtypes=[self.c.c_void_p];resume.restype=self.c.c_long
        if resume(int(process._handle))<0:raise OwnedProcessError('owned_process_resume_denied')
    def close(self):
        if not self.handle:return
        handles=[]
        try:
            # Closing a kill-on-close Job alone is asynchronous. Keep its handle
            # and read-only member handles until termination (including pending
            # process I/O cancellation) is confirmed. Enumerate this Job only.
            pids=self.Pids()
            if not self.k.QueryInformationJobObject(self.handle,3,self.c.byref(pids),self.c.sizeof(pids),None):
                raise OwnedProcessError('owned_job_members_unconfirmed')
            for pid in pids.ids[:pids.listed]:
                handle=self.k.OpenProcess(0x100000|0x1000,False,pid) # SYNCHRONIZE + QUERY_LIMITED_INFORMATION
                if not handle:
                    if self.c.get_last_error()==87:continue # already exited, no such process
                    raise OwnedProcessError('owned_job_member_handle_denied')
                handles.append(handle)
                member=self.c.c_int()
                if not self.k.IsProcessInJob(handle,self.handle,self.c.byref(member)) or not member.value:
                    raise OwnedProcessError('owned_job_member_identity_unconfirmed')
            if not self.k.TerminateJobObject(self.handle,1):
                raise OwnedProcessError('owned_job_termination_unconfirmed')
            until=time.monotonic()+10
            for handle in handles:
                wait=self.k.WaitForSingleObject(handle,max(0,int((until-time.monotonic())*1000)))
                if wait!=0:raise OwnedProcessError('owned_job_member_exit_unconfirmed')
            for handle in handles:self.k.CloseHandle(handle)
            handles=[]
            while True:
                info=self.Accounting()
                if not self.k.QueryInformationJobObject(self.handle,1,self.c.byref(info),self.c.sizeof(info),None):
                    raise OwnedProcessError('owned_job_quiescence_unconfirmed')
                if info.active==0:break
                if time.monotonic()>=until:raise OwnedProcessError('owned_job_quiescence_timeout')
                time.sleep(.01)
        finally:
            for handle in handles:self.k.CloseHandle(handle)
            self.k.CloseHandle(self.handle);self.handle=None

class OutputMetadata:
    """Drain a bounded pipe, retaining only digest/count and optional phase hints."""
    def __init__(self, pipe, limit, observer):
        self.pipe,self.limit,self.observer=pipe,limit,observer
        self.observed_bytes=0;self.digest=hashlib.sha256()
        self.complete=False;self.read_failed=False;self.observer_failed=False
        self.excess=False;self.first=False
        self.thread=threading.Thread(target=self._read,daemon=True)
    def notify(self, method, *args, **kw):
        if self.observer is None:return
        try:getattr(self.observer,method)(*args,**kw)
        except Exception:self.observer_failed=True
    def _read(self):
        try:
            read=getattr(self.pipe,'read1',self.pipe.read)
            while True:
                data=read(8192)
                if not data:self.complete=True;break
                self.observed_bytes+=len(data);self.digest.update(data)
                if not self.first:
                    self.first=True;self.notify('observe','output_first_byte')
                self.notify('feed',data)
                if self.observed_bytes>self.limit:self.excess=True;break
        except Exception:self.read_failed=True
    def metadata(self, returncode=None):
        return {'observed_bytes':self.observed_bytes,'sha256':self.digest.hexdigest(),
                'complete':self.complete and not self.read_failed and not self.excess,
                'read_failed':self.read_failed,'observer_failed':self.observer_failed,
                'returncode':returncode}


def run_owned(argv,*,input,stdout=None,stderr=None,timeout,check=False,output_limit=4_000_000,
              capture_metadata=False,observer=None):
    """Only argv (no shell). Timeout/output excess kills this whole owned tree."""
    if timeout<=0:raise ValueError('owned_timeout_invalid')
    if type(output_limit) is not int or output_limit<=0:raise ValueError('owned_output_limit_invalid')
    job=WindowsJob() if os.name=='nt' else None
    proc=None;capture=None;result=None;primary=None
    def observe(phase,**values):
        if capture:capture.notify('observe',phase,**values)
        elif observer:
            try:observer.observe(phase,**values)
            except Exception:pass
    try:
        with tempfile.TemporaryFile() as incoming:
            incoming.write(input);incoming.seek(0)
            kw={'creationflags':subprocess.CREATE_NO_WINDOW|4} if os.name=='nt' else {'start_new_session':True}
            observe('process_starting')
            proc=subprocess.Popen(argv,stdin=incoming,
                stdout=subprocess.PIPE if capture_metadata else stdout,
                stderr=subprocess.STDOUT if capture_metadata else stderr,**kw)
            if job:job.start(proc)
            if capture_metadata:
                capture=OutputMetadata(proc.stdout,output_limit,observer);capture.thread.start()
            observe('process_started')
            deadline=time.monotonic()+timeout
            next_checkpoint=time.monotonic()
            while proc.poll() is None:
                if capture:
                    if capture.excess:raise OwnedProcessError('owned_output_limit')
                    if capture.read_failed:raise OwnedProcessError('owned_output_read_failed')
                    if time.monotonic()>=next_checkpoint:
                        capture.notify('checkpoint');next_checkpoint=time.monotonic()+5
                elif os.fstat(stdout.fileno()).st_size>output_limit:raise OwnedProcessError('owned_output_limit')
                if time.monotonic()>=deadline:raise subprocess.TimeoutExpired(argv,timeout)
                time.sleep(min(.05,max(0,deadline-time.monotonic())))
            observe('process_exited',returncode=proc.returncode)
            if not capture and os.fstat(stdout.fileno()).st_size>output_limit:raise OwnedProcessError('owned_output_limit')
            result=subprocess.CompletedProcess(argv,proc.returncode)
            if check and proc.returncode:raise subprocess.CalledProcessError(proc.returncode,argv)
            return result
    except BaseException as exc:
        primary=exc
        raise
    finally:
        failures=[]
        observe('cleanup_started')
        try:
            if job:job.close() # also waits for descendants after successful parent exit
            elif proc:
                try:os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError:pass
        except Exception as exc:
            failures.append(str(exc) if isinstance(exc,OwnedProcessError) and re.fullmatch('owned_[a-z_]{1,80}',str(exc)) else 'owned_cleanup_failed')
        try:
            if proc:
                if proc.poll() is None:proc.kill()
                proc.wait(timeout=10)
        except Exception:failures.append('owned_parent_exit_unconfirmed')
        if capture:
            capture.thread.join(timeout=2)
            if capture.thread.is_alive():failures.append('owned_output_reader_unconfirmed')
            else:
                try:proc.stdout.close()
                except Exception:failures.append('owned_output_close_failed')
            if capture.excess and primary is None:primary=OwnedProcessError('owned_output_limit')
            if capture.read_failed and primary is None:primary=OwnedProcessError('owned_output_read_failed')
        observe('cleanup_unconfirmed' if failures else 'cleanup_complete')
        target=primary if primary is not None else result
        if target is not None:
            target.cleanup_confirmed=not failures
            target.cleanup_failure_codes=failures
            if capture:target.output_metadata=capture.metadata(proc.returncode if proc else None)
        # A secondary cleanup error must never replace the original timeout,
        # output limit, spawn or read error. A success with uncertain cleanup
        # remains blocked. Never return approval merely because a parent exited.
        if failures and primary is None:
            error=OwnedProcessError(failures[0]);error.cleanup_confirmed=False
            error.cleanup_failure_codes=failures
            if capture:error.output_metadata=capture.metadata(proc.returncode if proc else None)
            raise error
        if primary is not None and result is not None:raise primary
