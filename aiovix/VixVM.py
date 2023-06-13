import asyncio
import collections
from multiprocessing import Event

from .VixError import VixError
from .VixHandle import VixHandle
from .VixSnapshot import VixSnapshot
from .VixJob import VixJob
from aiovix import _backend, API_ENCODING
vix = _backend._vix
ffi = _backend._ffi


def _blocking_job(f):
    def decorator(*args, **kwargs):
        job = f(*args, **kwargs)
        VixJob(job).wait()

    # allows sphinx to generate docs normally...
    decorator.__doc__ = f.__doc__

    return decorator

DirectoryListEntry = collections.namedtuple('DirectoryListEntry', 'name size is_dir is_sym last_mod')
ProcessListEntry = collections.namedtuple('ProcessListEntry', 'name pid owner cmd is_debug start_time')
SharedFolder = collections.namedtuple('SharedFolder', 'name host_path write_access')
Process = collections.namedtuple('Process', 'pid exit_code elapsed_time')

from threading import Event, Lock
_proc_jobs_lock = Lock()
_proc_jobs = dict()
_idx = 1

class _ProcJob():
    pid = None
    exit_code = None
    elapsed_time = None

    def __init__(self) -> None:
        self._done_evt = Event()

        global _proc_jobs_lock
        _proc_jobs_lock.acquire(blocking=True)
        global _idx
        self._id = _idx
        _idx += 1

        global _proc_jobs
        _proc_jobs[self._id] = self
        _proc_jobs_lock.release()

    def id(self):
        return self._id

    @staticmethod
    def by_id(id):
        global _proc_jobs
        _proc_jobs_lock.acquire(blocking=True)
        job = _proc_jobs.get(id)
        _proc_jobs_lock.release()
        return job

    def wait(self):
        self._done_evt.wait()
    
    async def wait(self):
        coro = asyncio.to_thread(self.wait)
        await asyncio.create_task(coro)


class VixVM(VixHandle):
    """Represents a guest VM."""
    
    _VIX_VMDELETE_DISK_FILES = 0x0002

    VIX_POWERSTATE_POWERING_OFF = 0x0001
    VIX_POWERSTATE_POWERED_OFF = 0x0002
    VIX_POWERSTATE_POWERING_ON = 0x0004
    VIX_POWERSTATE_POWERED_ON = 0x0008
    VIX_POWERSTATE_SUSPENDING = 0x0010
    VIX_POWERSTATE_SUSPENDED = 0x0020
    VIX_POWERSTATE_TOOLS_RUNNING = 0x0040
    VIX_POWERSTATE_RESETTING = 0x0080
    VIX_POWERSTATE_BLOCKED_ON_MSG = 0x0100
    VIX_POWERSTATE_PAUSED = 0x0200
    VIX_POWERSTATE_RESUMING = 0x0800

    VIX_TOOLSSTATE_UNKNOWN = 0x0001
    VIX_TOOLSSTATE_RUNNING = 0x0002
    VIX_TOOLSSTATE_NOT_INSTALLED = 0x0004

    VIX_VM_SUPPORT_SHARED_FOLDERS = 0x0001
    VIX_VM_SUPPORT_MULTIPLE_SNAPSHOTS = 0x0002
    VIX_VM_SUPPORT_TOOLS_INSTALL = 0x0004
    VIX_VM_SUPPORT_HARDWARE_UPGRADE = 0x0008

    _VIX_LOGIN_IN_GUEST_REQUIRE_INTERACTIVE_ENVIRONMENT = 0x08

    _VIX_RUNPROGRAM_RETURN_IMMEDIATELY = 0x0001
    _VIX_RUNPROGRAM_ACTIVATE_WINDOW = 0x0002

    VIX_VM_GUEST_VARIABLE = 1
    VIX_VM_CONFIG_RUNTIME_ONLY = 2
    VIX_GUEST_ENVIRONMENT_VARIABLE = 3

    _VIX_SNAPSHOT_REMOVE_CHILDREN = 0x0001

    _VIX_SNAPSHOT_INCLUDE_MEMORY = 0x0002

    _VIX_SHAREDFOLDER_WRITE_ACCESS = 0x04

    _VIX_CAPTURESCREENFORMAT_PNG = 0x01
    _VIX_CAPTURESCREENFORMAT_PNG_NOCOMPRESS = 0x02

    _VIX_CLONETYPE_FULL = 0
    _VIX_CLONETYPE_LINKED = 1

    _VIX_INSTALLTOOLS_MOUNT_TOOLS_INSTALLER = 0x00
    _VIX_INSTALLTOOLS_AUTO_UPGRADE = 0x01
    _VIX_INSTALLTOOLS_RETURN_IMMEDIATELY = 0x02

    VIX_VMPOWEROP_NORMAL = 0
    VIX_VMPOWEROP_FROM_GUEST = 0x0004
    VIX_VMPOWEROP_SUPPRESS_SNAPSHOT_POWERON = 0x0080
    VIX_VMPOWEROP_LAUNCH_GUI = 0x0200
    VIX_VMPOWEROP_START_VM_PAUSED = 0x1000

    def __init__(self, handle):
        super(VixVM, self).__init__(handle)

        assert self.get_type() == VixHandle.VIX_HANDLETYPE_VM, 'Expected VixVM handle.'

    @property
    def vmx_path(self):
        """Gets VM'x vmx path.

        :returns: Guest's VMX path.
        :rtype: str
        """

        return self.get_properties(VixHandle.VIX_PROPERTY_VM_VMX_PATHNAME)

    @property
    def machine_info(self):
        """Get the VM's hardware specs

        :returns: a tuple: (num_cpus, memory)
        :rtype: tuple
        """

        return self.get_properties(
            VixHandle.VIX_PROPERTY_VM_NUM_VCPUS, 
            VixHandle.VIX_PROPERTY_VM_MEMORY_SIZE
        )

    @property
    def is_running(self):
        """Checks if VM is running

        :returns: True if running otherwise False.
        :rtype: bool
        """

        return self.get_properties(VixHandle.VIX_PROPERTY_VM_IS_RUNNING)

    @property
    def guest_os(self):
        """The guest's Operating System

        :rtype: str
        """

        return self.get_properties(VixHandle.VIX_PROPERTY_VM_GUESTOS)

    @property
    def name(self):
        """Name of the VM.

        :rtype: str
        """

        return self.get_properties(VixHandle.VIX_PROPERTY_VM_NAME)

    @property
    def is_readonly(self):
        """Checks if the VM is readonly.

        :rtype: bool
        """

        return self.get_properties(VixHandle.VIX_PROPERTY_VM_READ_ONLY)

    @property
    def power_state(self):
        """Gets the VMs power state.

        :returns: Any of VixVM.VIX_VM_POWERSTATE_*
        :rtype: int
        """

        return self.get_properties(VixHandle.VIX_PROPERTY_VM_POWER_STATE)

    @property
    def tools_state(self):
        """Get the VMware tools state.

        :returns: Any of VixVM.VIX_VM_TOOLSSTATE_*
        :rtype: int
        """

        return self.get_properties(VixHandle.VIX_PROPERTY_VM_TOOLS_STATE)

    @property
    def supported_features(self):
        """Get features supported by the VM.

        :returns: Any of VixVM.VIX_VM_SUPPORT_*.
        :rtype: int
        """
        return self.get_properties(VixHandle.VIX_PROPERTY_VM_SUPPORTED_FEATURES)

    def __repr__(self):
        return "<VixVM @ {0}>".format(self.vmx_path)

    # Power
    async def pause(self):
        """Pauses the Virtual machine.

        .. note:: This method is not supported by all VMware products.
        """

        job = vix.VixVM_Pause(
            self._handle,
            ffi.cast('int', 0),
            ffi.cast('VixHandle', 0),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        )

        return await VixJob(job).wait_async()

    async def power_off(self, from_guest=False):
        """Powers off a VM.

        :param bool from_guest: True to initiate from guest, otherwise False.

        :raises vix.VixError: On failure to power off VM.
        """

        job = vix.VixVM_PowerOff(
            self._handle,
            ffi.cast('VixVMPowerOpOptions', self.VIX_VMPOWEROP_FROM_GUEST if from_guest else self.VIX_VMPOWEROP_NORMAL),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        )

        return await VixJob(job).wait_async()

    async def power_on(self, launch_gui=False):
        """Powers on a VM.

        :param bool launch_gui: True to launch GUI, otherwise False.

        :raises vix.VixError: On failure to power on VM.
        """

        job = vix.VixVM_PowerOn(
            self._handle,
            ffi.cast('VixVMPowerOpOptions', self.VIX_VMPOWEROP_LAUNCH_GUI if launch_gui else self.VIX_VMPOWEROP_NORMAL),
            ffi.cast('VixHandle', 0),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        )

        return await VixJob(job).wait_async()

    async def reset(self, from_guest=False):
        """Resets a virtual machine.

        :param bool from_guest: True to initiate from guest, otherwise False.

        :raises vix.VixError: On failure to reset VM.
        """

        job = vix.VixVM_Reset(
            self._handle,
            ffi.cast('VixVMPowerOpOptions', self.VIX_VMPOWEROP_FROM_GUEST if from_guest else self.VIX_VMPOWEROP_NORMAL),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        )
        
        return await VixJob(job).wait_async()

    async def suspend(self):
        """Suspends a virtual machine.

        :raises vix.VixError: On failure to suspend VM.
        """

        job = vix.VixVM_Suspend(
            self._handle,
            ffi.cast('VixVMPowerOpOptions', 0),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        )

        return await VixJob(job).wait_async()

    async def unpause(self):
        """Resumes execution of a paused virtual machine.

        :raises vix.VixError: On failure to unpause VM.

        .. note:: This method is not supported by all Vmware products.
        """

        job = vix.VixVM_Unpause(
            self._handle,
            ffi.cast('int', 0),
            ffi.cast('VixHandle', 0),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        )
        
        return await VixJob(job).wait_async()

    # Snapshots
    async def clone(self, dest_vmx, snapshot=None, linked=False):
        """Clones the VM to a specified location.

        :param str dest_vms: The clone will be stored here.
        :param .VixSnapshot snapshot: Optional snapshot as the state of the clone.
        :param bool linked: True for a linked clone, otherwise False for a full clone.

        :returns: Instance of the cloned VM.
        :rtype: .VixVM

        :raises vix.VixError: On failure to clone.

        .. note:: This method is not supported by all VMware products.
        """

        job = vix.VixVM_Clone(
            self._handle,
            ffi.cast('VixHandle', snapshot._handle if snapshot else 0),
            ffi.cast('VixCloneType', self._VIX_CLONETYPE_LINKED if linked else self._VIX_CLONETYPE_FULL),
            ffi.new('char[]', bytes(dest_vmx, API_ENCODING)),
            ffi.cast('int', 0),
            ffi.cast('VixHandle', 0),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        )
    
        handle = await VixJob(job).wait_async(VixJob.VIX_PROPERTY_JOB_RESULT_HANDLE)
        return VixVM(handle)

    async def create_snapshot(self, name=None, description=None, include_memory=True):
        """Create a VM snapshot.

        :param str name: Name of snapshot.
        :param str description: Snapshot description.
        :param bool include_memory: True to include RAM, otherwise False.

        :returns: Instance of the created snapshot
        :rtype: .VixSnapshot

        :raises vix.VixError: On failure to create snapshot.

        .. note:: This method is not supported by all VMware products.
        """

        job = vix.VixVM_CreateSnapshot(
            self._handle,
            ffi.new('char[]', bytes(name, API_ENCODING)) if name else ffi.cast('char*', 0),
            ffi.new('char[]', bytes(description, API_ENCODING)) if description else  ffi.cast('char*', 0),
            ffi.cast('int', self._VIX_SNAPSHOT_INCLUDE_MEMORY if include_memory else 0),
            ffi.cast('VixHandle', 0),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        )

        handle = await VixJob(job).wait_async(VixJob.VIX_PROPERTY_JOB_RESULT_HANDLE)
        return VixSnapshot(handle)

    def snapshot_get_current(self):
        """Gets the VMs current active snapshot.

        :returns: The currently active snapshot
        :rtype: .VixSnapshot

        :raises vix.VixError: On failure to get the current snapshot.

        .. note:: This method is not supported by all VMware products.
        """

        snapshot_handle = ffi.new('VixHandle*')
        error_code = vix.VixVM_GetCurrentSnapshot(
            self._handle,
            snapshot_handle,
        )

        if error_code != VixError.VIX_OK:
            raise VixError(error_code)

        return VixSnapshot(snapshot_handle[0])

    def snapshot_get_named(self, name):
        """Gets a snapshot matching the given name.

        :param str name: Name of the snapshot to get.
        
        :returns: Instance of requests snapshot.
        :rtype: .VixSnapshot

        :raises vix.VixError: If failed to retreive desired snapshot.

        .. note:: This method is not supported by all VMware products.
        """

        snapshot_handle = ffi.new('VixHandle*')
        error_code = vix.VixVM_GetNamedSnapshot(
            self._handle,
            ffi.new('char[]', bytes(name, API_ENCODING)),
            snapshot_handle,
        )

        if error_code != VixError.VIX_OK:
            raise VixError(error_code)

        return VixSnapshot(snapshot_handle[0])

    def snapshots_get_root_count(self):
        """Gets the count of root snapshots the VM owns.

        :returns: Count of VM's root snapshots.
        :rtype: int

        :raises vix.VixError: If failed to retrive root snapshot count.

        .. note:: This method is not supported by all VMware products.
        """

        result = ffi.new('int*')
        error_code = vix.VixVM_GetNumRootSnapshots(
            self._handle,
            result,
        )

        if error_code != VixError.VIX_OK:
            raise VixError(error_code)

        return result[0]

    def snapshot_get_root(self, index=0):
        """Gets the specified VM Snapshot.

        :param int index: zero based snapshot index.

        :returns: Root snapshot at specified index.
        :rtype: .VixSnapshot

        :raises vix.VixError: If failed to get specified too snapshot.

        .. note:: This methoid is not supported in all VMware products.
        """

        snapshot_handle = ffi.new('VixHandle*')
        error_code = vix.VixVM_GetRootSnapshot(
            self._handle,
            ffi.cast('int', index),
            snapshot_handle,
        )

        if error_code != VixError.VIX_OK:
            raise VixError(error_code)

        return VixSnapshot(snapshot_handle[0])

    async def snapshot_revert(self, snapshot, options=0):
        """Revet VM state to specified snapshot.

        :param .VixSnapshot snapshot: The snapshot to revert to.
        :param int options: Any of VIX_VMPOWEROP_*, VIX_VMPOWEROP_SUPPRESS_SNAPSHOT_POWERON is mutually exclusive.

        :raises vix.VixError: If failed to revert VM to snapshot.

        .. note:: This method is not supported by all VMware products.
        """

        job = vix.VixVM_RevertToSnapshot(
            self._handle,
            snapshot._handle,
            ffi.cast('int', options),
            ffi.cast('VixHandle', 0),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        )
        
        return await VixJob(job).wait_async()

    async def snapshot_remove(self, snapshot, remove_children=False):
        """Removed specified snapshot from VM.

        :param .VixSnapshot snapshot: The snapshot to remove.
        :param bool remove_children: True to remove child snapshots too, otherwise False.

        :raises vix.VixError: If failed to remove specified snapshot.

        .. note:: This method is not supported by all VMware products.
        """

        job = vix.VixVM_RemoveSnapshot(
            self._handle,
            snapshot._handle,
            ffi.cast('int', self._VIX_SNAPSHOT_REMOVE_CHILDREN if remove_children else 0),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        )
        
        return await VixJob(job).wait_async()

    # Guest & Host file mgmt.
    async def copy_guest_to_host(self, guest_path, host_path):
        """Copies a file or directory from the VM to host.

        :param str guest_path: Path to copy from on guest.
        :param str host_path: Path to copy to on host.

        :raises vix.VixError: If copy failed.
        """

        job = vix.VixVM_CopyFileFromGuestToHost(
            self._handle,
            ffi.new('char[]', bytes(guest_path, API_ENCODING)),
            ffi.new('char[]', bytes(host_path, API_ENCODING)),
            ffi.cast('int', 0),
            ffi.cast('VixHandle', 0),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        )
        
        return await VixJob(job).wait_async()

    async def copy_host_to_guest(self, host_path, guest_path):
        """Copies a file or directory from host to VM.

        :param str host_path: Path to copy from on host.
        :param str guest_path: Path to copy to on VM.

        :raises vix.VixError: If failed to copy.
        """

        job = vix.VixVM_CopyFileFromHostToGuest(
            self._handle,
            ffi.new('char[]', bytes(host_path, API_ENCODING)),
            ffi.new('char[]', bytes(guest_path, API_ENCODING)),
            ffi.cast('int', 0),
            ffi.cast('VixHandle', 0),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        )
        
        return await VixJob(job).wait_async()

    @_blocking_job
    def create_directory(self, path):
        """Creates a directory in the guest VM.

        :param str path: Path to create in guest.

        :raises vix.VixError: On failure to create directory.

        .. note:: This method is not supported by all VMware products.
        """

        return vix.VixVM_CreateDirectoryInGuest(
            self._handle,
            ffi.new('char[]', bytes(path, API_ENCODING)),
            ffi.cast('VixHandle', 0),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        )

    def create_temp(self):
        """Creates a temporary file in guest.

        :returns: Temporary file name.
        :rtype: str

        :raises vix.VixError: On failure to create temporary file.

        .. note:: This method is not supported by all VMware products.
        """

        job = VixJob(vix.VixVM_CreateTempFileInGuest(
            self._handle,
            ffi.cast('int', 0),
            ffi.cast('VixHandle', 0),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        ))

        return job.wait(VixJob.VIX_PROPERTY_JOB_RESULT_ITEM_NAME)

    @_blocking_job
    def file_rename(self, old_name, new_name):
        """Renames a file or directory in guest.

        :param str old_name: Name of file to rename.
        :param str new_name: The new name to give the file.

        :raises vix.VixError: On failure to rename.

        .. note:: This method is not supported by all VMware products.
        """

        return vix.VixVM_RenameFileInGuest(
            self._handle,
            ffi.new('char[]', bytes(old_name, API_ENCODING)),
            ffi.new('char[]', bytes(new_name, API_ENCODING)),
            ffi.cast('int', 0),
            ffi.cast('VixHandle', 0),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        )

    @_blocking_job
    def dir_delete(self, path):
        """Deletes a directory in guest VM.

        :param str path: Path of directory to delete.

        :raises vix.VixError: If failed to delete directory.

        .. note:: This method is not supported by all VMware products.
        """

        return vix.VixVM_DeleteDirectoryInGuest(
            self._handle,
            ffi.new('char[]', bytes(path, API_ENCODING)),
            ffi.cast('int', 0),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        )

    @_blocking_job
    def file_delete(self, path):
        """Deletes a file in guest VM.

        :param str path: Path of file to delete.

        :raises vix.VixError: If failed to delete directory.

        .. note:: This method is not supported by all VMware products.
        """

        return vix.VixVM_DeleteFileInGuest(
            self._handle,
            ffi.new('char[]', bytes(path, API_ENCODING)),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        )

    def dir_exists(self, path):
        """Checks if a directory exists in guest VM.

        :param str path: Path to check if exists.

        :returns: True if directory exists, othwerwise False.
        :rtype: bool

        :raises vix.VixError: If failed to check.

        .. note:: This method is not supported by all VMware products.
        """

        job = VixJob(vix.VixVM_DirectoryExistsInGuest(
            self._handle,
            ffi.new('char[]', bytes(path, API_ENCODING)),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        ))

        return bool(job.wait(VixJob.VIX_PROPERTY_JOB_RESULT_GUEST_OBJECT_EXISTS))

    def file_exists(self, path):
        """Checks if a file exists in guest VM.

        :param str path: File to check.

        :returns: True if file exists, otherwise False.
        :rtype: bool

        :raises vix.VixError: If failed to check file existance.

        .. note:: This method is not supported by all VMware products.
        """

        job = VixJob(vix.VixVM_FileExistsInGuest(
            self._handle,
            ffi.new('char[]', bytes(path, API_ENCODING)),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        ))

        return bool(job.wait(VixJob.VIX_PROPERTY_JOB_RESULT_GUEST_OBJECT_EXISTS))

    def get_file_info(self, path):
        """Gets information about specified file in guest.

        :param str path: File path to get information about.

        :returns: DirectoryListEntry instance.
        :rtype: .DirectoryListEntry

        :raises vix.VixError: On failure to get file info.

        .. note:: This method is not supported by all VMware products.
        """

        job = VixJob(vix.VixVM_GetFileInfoInGuest(
            self._handle,
            ffi.new('char[]', bytes(path, API_ENCODING)),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        ))
        job.wait()
        res = job.get_properties(
            VixJob.VIX_PROPERTY_JOB_RESULT_FILE_SIZE,
            VixJob.VIX_PROPERTY_JOB_RESULT_FILE_FLAGS,
            VixJob.VIX_PROPERTY_JOB_RESULT_FILE_MOD_TIME,
        )
        assert len(res) == 1, 'Expected single result'
        res = res[0]
        return DirectoryListEntry(
            name=None,
            size=res[0],
            is_dir=bool(res[1] & VixJob.VIX_FILE_ATTRIBUTES_DIRECTORY),
            is_sym=bool(res[1] & VixJob.VIX_FILE_ATTRIBUTES_SYMLINK),
            last_mod=res[2],
        )

    def dir_list(self, path):
        """Gets directory listing of specified path in guest VM.

        :param str path: Path to get directory list of.

        :returns: List of tuples, each containing: File Name, File Size, is dir, is symlink, mod time.

        :raises vix.VixError: On failure to get file info.

        .. note:: This method is not supported by all VMware products.
        """

        job = VixJob(vix.VixVM_ListDirectoryInGuest(
            self._handle,
            ffi.new('char[]', bytes(path, API_ENCODING)),
            ffi.cast('int', 0),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        ))
        job.wait()
        
        job_result = job.get_properties(
            VixJob.VIX_PROPERTY_JOB_RESULT_ITEM_NAME,
            VixJob.VIX_PROPERTY_JOB_RESULT_FILE_SIZE,
            VixJob.VIX_PROPERTY_JOB_RESULT_FILE_FLAGS,
            VixJob.VIX_PROPERTY_JOB_RESULT_FILE_MOD_TIME,
        )

        result = list()

        for res in job_result:
            result.append(DirectoryListEntry(
                name=res[0],
                size=res[1],
                is_dir=bool(res[2] & VixJob.VIX_FILE_ATTRIBUTES_DIRECTORY),
                is_sym=bool(res[2] & VixJob.VIX_FILE_ATTRIBUTES_SYMLINK),
                last_mod=res[3],
            ))

        return result

    # Guest execution
    async def proc_kill(self, pid):
        """Kills a process in guest VM.

        :param int pid: PID of process in guest to kill.

        :raises vix.VixError: If failed to kill process.

        .. note:: This method is not supported by all VMware products.
        """

        job = vix.VixVM_KillProcessInGuest(
            self._handle,
            ffi.cast('uint64', pid),
            ffi.cast('int', 0),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        )
        
        return await VixJob(job).wait_async()

    def proc_list(self):
        """Gets the guest's process list.

        :returns: A list of tuples, each tuple contains: Process Name, PID, owner, cmd line, is debugged, start time.
        :rtype: list

        :raises vix.VixError: On failure to get file info.

        .. note:: This method is not supported by all VMware products.
        """

        job = VixJob(vix.VixVM_ListProcessesInGuest(
            self._handle,
            ffi.cast('int', 0),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        ))

        job.wait()

        return [ProcessListEntry(
            name=entry[0],
            pid=entry[1],
            owner=entry[2],
            cmd=entry[3],
            is_debug=entry[4],
            start_time=entry[5],
        ) for entry in job.get_properties(
            VixJob.VIX_PROPERTY_JOB_RESULT_ITEM_NAME,
            VixJob.VIX_PROPERTY_JOB_RESULT_PROCESS_ID,
            VixJob.VIX_PROPERTY_JOB_RESULT_PROCESS_OWNER,
            VixJob.VIX_PROPERTY_JOB_RESULT_PROCESS_COMMAND,
            VixJob.VIX_PROPERTY_JOB_RESULT_PROCESS_BEING_DEBUGGED,
            VixJob.VIX_PROPERTY_JOB_RESULT_PROCESS_START_TIME,
        )]

    async def login(self, username, password, require_interactive=False):
        """Login to the guest to allow further executions.

        :param str username: Guest Login username.
        :param str password: Guest login password.
        :param bool require_interactive: If login requires an interactive session.

        :raises vix.VixError: On failure to authenticate.
        """

        job = vix.VixVM_LoginInGuest(
            self._handle,
            ffi.new('char[]', bytes(username, API_ENCODING)) if username else ffi.cast('char*', 0),
            ffi.new('char[]', bytes(password, API_ENCODING)) if password else ffi.cast('char*', 0),
            ffi.cast('int', self._VIX_LOGIN_IN_GUEST_REQUIRE_INTERACTIVE_ENVIRONMENT if require_interactive else 0),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        )
        
        return await VixJob(job).wait_async()

    async def logout(self):
        """Logout from guest. Closes any previous login context.

        :raises vix.VixError: If failed to logout.

        .. note:: This method is not supported by all VMware products.
        """

        job = vix.VixVM_LogoutFromGuest(
            self._handle,
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        )
        
        return await VixJob(job).wait_async()

    async def proc_run(self, program_name, command_line=None, should_block=True) -> Process:
        """Executes a process in guest VM.

        :param str program_name: Name of program to execute in guest.
        :param str command_line: Command line to execute program with.
        :param bool should_block: If set to True, function will block until process exits in guest. If set to False - the returned `_ProcJob` will not have the exit_code or elapsed_time set.

        :returns: _ProcJob.

        :raises vix.VixError: On failure to execute process.

        .. note:: This method is not supported by all VMware products.
        """

        pj = _ProcJob()

        job = vix.VixVM_RunProgramInGuest(
            self._handle,
            ffi.new('char[]', bytes(program_name, API_ENCODING)),
            ffi.new('char[]', bytes(command_line, API_ENCODING)) if command_line else ffi.cast('char*', 0),
            ffi.cast('VixRunProgramOptions', 0 if should_block else self._VIX_RUNPROGRAM_RETURN_IMMEDIATELY),
            ffi.cast('VixHandle', 0),
            ffi.cast('VixEventProc*', _callback_handler),
            ffi.cast('void*', pj.id()),
        )
        pid = await VixJob(job).wait_async(VixJob.VIX_PROPERTY_JOB_RESULT_PROCESS_ID)

        if should_block:
            pj.pid = pid
            pj.wait()  # TODO shouldmake this awaitable
            return Process(pid, pj.exit_code, pj.elapsed_time)
        else:
            return Process(pid, None, None)

    async def run_script(self, script_text, interpreter_path=None, should_block=True):
        """Executes a script in guest VM.

        :param str script_text: The script to execute.
        :param str interpreter_path: Path of the interpreter for the script.
        :param bool should_block: If set to False, function will return immediately. True will block untill script returns.

        :raises vix.VixError: On failure to execute script.

        .. note:: This method is not supported by all VMware products.
        """

        pj = _ProcJob()
        job = vix.VixVM_RunScriptInGuest(
            self._handle,
            ffi.new('char[]', bytes(interpreter_path, API_ENCODING)) if interpreter_path else ffi.cast('char*', 0),
            ffi.new('char[]', bytes(script_text, API_ENCODING)),
            ffi.cast('VixRunProgramOptions', 0 if should_block else self._VIX_RUNPROGRAM_RETURN_IMMEDIATELY),
            ffi.cast('VixHandle', 0),
            ffi.cast('VixEventProc*', _callback_handler),
            ffi.cast('void*', pj.id()),
        )
        pid = await VixJob(job).wait_async(VixJob.VIX_PROPERTY_JOB_RESULT_PROCESS_ID)

        if should_block:
            pj.pid = pid
            pj.wait()
            return Process(pid, pj.exit_code, pj.elapsed_time)
        else:
            return Process(pid, None, None)

    # Share mgmt.
    @_blocking_job
    def add_shared_folder(self, share_name, host_path, write_access=True):
        """Shares a folder with the guest VM.

        :param str share_name: Name of share in guest VM.
        :param str host_path: Path to share in host.
        :param bool write_access: True to allow guest to write to share.

        :raises vix.VixError: On failure to add share.

        .. note:: This method is not supported by all VMware products.
        """

        # TODO: return the path of shared folder in guest.
        return vix.VixVM_AddSharedFolder(
            self._handle,
            ffi.new('char[]', bytes(share_name, API_ENCODING)),
            ffi.new('char[]', bytes(host_path, API_ENCODING)),
            ffi.cast('VixMsgSharedFolderOptions', self._VIX_SHAREDFOLDER_WRITE_ACCESS if write_access else 0),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        )

    @_blocking_job
    def share_enable(self, value=True):
        """Enables/Disables shares between Host and guest VM.

        :param bool value: True to enable, False to disable.

        :raises vix.VixError: If failed to enable/disable shares.

        .. note:: This method is not supported by all VMware products.
        """

        return vix.VixVM_EnableSharedFolders(
            self._handle,
            ffi.cast('Bool', int(value)),
            ffi.cast('int', 0),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        )

    def get_shared_folder_count(self):
        """Gets the count of shared folder of VM with host.

        .. note:: This method is not supported by all VMware products.
        """

        return VixJob(vix.VixVM_GetNumSharedFolders(
            self._handle,
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        )).wait(VixJob.VIX_PROPERTY_JOB_RESULT_SHARED_FOLDER_COUNT)

    def get_shared_folder_state(self, index):
        """Gets the state of a shared folder.

        :param int index: Index of share.

        :returns: tuple with share state information.
        :rtype: SharedFolder

        :raises vix.VixError: If failed to get state.

        .. note:: This method is not supported by all VMware products.
        """

        job = VixJob(vix.VixVM_GetSharedFolderState(
            self._handle,
            ffi.cast('int', index),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        ))
        job.wait()
        res = job.get_properties(
            VixJob.VIX_PROPERTY_JOB_RESULT_ITEM_NAME,
            VixJob.VIX_PROPERTY_JOB_RESULT_SHARED_FOLDER_HOST,
            VixJob.VIX_PROPERTY_JOB_RESULT_SHARED_FOLDER_FLAGS,
        )
        assert len(res) == 1, 'Expected single result'
        res = res[0]
        return SharedFolder(
            name=res[0],
            host_path=res[1],
            write_access=bool(res[2] & VixVM._VIX_SHAREDFOLDER_WRITE_ACCESS),
        )

    @_blocking_job
    def share_remove(self, share_name):
        """Removes a share between host and guest VM.

        :param str share_name: Name of share to remove.

        .. note:: This method is not supported by all VMware products.
        """

        return vix.VixVM_RemoveSharedFolder(
            self._handle,
            ffi.new('char[]', bytes(share_name, API_ENCODING)),
            ffi.cast('int', 0),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        )

    @_blocking_job
    def share_set_state(self, share_name, host_path, allow_write=True):
        """Sets the state for an existing share.

        :param str share_name: Name of share to modify.
        :param str host_path: Path on host to set to share.
        :param bool allow_write: Sets if the guest will be able to write to share.

        :raises vix.VixError: If failed to set share state.

        .. note:: This method is not supported by all VMware products.
        """

        return vix.VixVM_SetSharedFolderState(
            self._handle,
            ffi.new('char[]', bytes(share_name, API_ENCODING)),
            ffi.new('char[]', bytes(host_path, API_ENCODING)),
            ffi.cast('VixMsgSharedFolderOptions', VixVM._VIX_SHAREDFOLDER_WRITE_ACCESS if allow_write else 0),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        )

    # VM environment.
    def var_read(self, name, variable_type=VIX_VM_GUEST_VARIABLE):
        """Reads an environment string.

        :param str name: Name of variable to read.
        :param int variable_type: Must be one of VIX_VM_GUEST_VARIABLE, VIX_VM_CONFIG_RUNTIME_ONLY or VIX_GUEST_ENVIRONMENT_VARIABLE.

        :returns: The value of the variable.
        :rtype: str

        :raises vix.VixError: On failure to get specified variable.

        .. note:: This method is not supported by all VMware products.
        """

        job = VixJob(vix.VixVM_ReadVariable(
            self._handle,
            ffi.cast('int', variable_type),
            ffi.new('char[]', bytes(name, API_ENCODING)),
            ffi.cast('int', 0),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        ))

        return job.wait(VixJob.VIX_PROPERTY_JOB_RESULT_VM_VARIABLESTRING)

    @_blocking_job
    def var_write(self, name, value, variable_type=VIX_VM_GUEST_VARIABLE):
        """Writes a string to the VM's environment.

        :param str name: Name of env string to set.
        :param str value: Value of env string to set.
        :param int variable_type: Must be one of VIX_VM_GUEST_VARIABLE, VIX_VM_CONFIG_RUNTIME_ONLY or VIX_GUEST_ENVIRONMENT_VARIABLE.

        :raises vix.VixError: On failure to set environment.

        .. note:: This method is not supported by all VMware products.
        """

        return vix.VixVM_WriteVariable(
            self._handle,
            ffi.cast('int', variable_type),
            ffi.new('char[]', bytes(name, API_ENCODING)),
            ffi.new('char[]', bytes(value, API_ENCODING)),
            ffi.cast('int', 0),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        )

    # Misc. methods
    @_blocking_job
    def upgrade_virtual_hardware(self):
        """Upgrades virtual hardware of a virtual machine.

        :raises vix.VixError: If failed to upgrade virtual hardware.

        .. note:: This method is not supported by all VMware products.
        """

        return vix.VixVM_UpgradeVirtualHardware(
            self._handle,
            ffi.cast('int', 0),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        )

    async def vm_delete(self, delete_files=False):
        """Deletes VM from host.

        :param bool delete_files: True to delete associated files from disk, otherwise False.

        :raises vix.VixError: If failed to delete VM.
        """

        job = vix.VixVM_Delete(
            self._handle,
            ffi.cast('VixVMDeleteOptions', self._VIX_VMDELETE_DISK_FILES if delete_files else 0),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        )

        await VixJob(job).wait_async()

    def capture_screen_image(self, filename=None):
        """Captures a PNG screenshot from VM.

        :param str filename: A filename to save image to. If this file exists it will be overwritten. None will return the image a string/BLOB.

        :returns: A PNG image in binary form if filename is None, otherwise None
        :rtype: bytes

        :raises vix.VixError: On failure to capture screenshot.

        .. note:: This method is not supported by all VMWare products.
        """

        job = VixJob(vix.VixVM_CaptureScreenImage(
            self._handle,
            ffi.cast('int', self._VIX_CAPTURESCREENFORMAT_PNG),
            ffi.cast('VixHandle', 0),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        ))

        bytes_ptr = ffi.new('int*')
        data_ptr = ffi.new('char**')

        error_code = vix.VixJob_Wait(
            job._handle,
            ffi.cast('int', VixJob.VIX_PROPERTY_JOB_RESULT_SCREEN_IMAGE_DATA),
            bytes_ptr,
            data_ptr,
            ffi.cast('int', VixJob.VIX_PROPERTY_NONE)
        )

        if error_code != VixError.VIX_OK:
            raise VixError(error_code)

        img_len = int(bytes_ptr[0])
        img_data = bytes(ffi.buffer(data_ptr[0], img_len))

        vix.Vix_FreeBuffer(data_ptr[0])

        if filename:
            with open(filename, "wb") as fd:
                fd.write(img_data)
        else:
            return img_data

    # VMware tools
    async def wait_for_tools(self, timeout=0):
        """Waits for VMware tools to start in guest.

        :param int timeout: Timeout in seconds. Zero or negative will block forever, Raises an exception if timeout expired.

        :raises vix.VixError: If timeout passed, Or of VIX fails.
        """

        job = vix.VixVM_WaitForToolsInGuest(
            self._handle,
            ffi.cast('int', timeout),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        )
        await VixJob(job).wait_async()


    @_blocking_job
    def install_tools(self, auto_upgrade=False, blocking=True):
        """Starts the VMware tools install operation on guest.

        :param bool auto_upgrade: True for auto upgrade, False will mount installer.
        :param bool blocking: False will return immediatly, True will wait till operation ends.

        :raises vix.VixError: On failure to start install.
        """

        options = 0
        if blocking:
            options |= self._VIX_INSTALLTOOLS_RETURN_IMMEDIATELY
        if auto_upgrade:
            options |= self._VIX_INSTALLTOOLS_AUTO_UPGRADE

        return vix.VixVM_InstallTools(
            self._handle,
            ffi.cast('int', options),
            ffi.cast('char*', 0),
            ffi.cast('VixEventProc*', 0),
            ffi.cast('void*', 0),
        )

    def __del__(self):
        self.release()

@_backend._ffi.callback('VixEventProc')
def _callback_handler(a, event_type, props, d):
    from .VixHandle import VixHandle

    VIX_EVENTTYPE_JOB_COMPLETED = 2
    VIX_EVENTTYPE_JOB_PROGRESS = 3

    handle = VixHandle(a)
    job_id = int(ffi.cast('size_t', d))
    job = _ProcJob.by_id(job_id)
    if not job:
        raise ValueError('Got callback event for non-existent job')

    if event_type == VIX_EVENTTYPE_JOB_PROGRESS:
        pass
    elif event_type == VIX_EVENTTYPE_JOB_COMPLETED:
        props = handle.get_properties(
            VixJob.VIX_PROPERTY_JOB_RESULT_PROCESS_ID,
            VixJob.VIX_PROPERTY_JOB_RESULT_GUEST_PROGRAM_EXIT_CODE, 
            VixJob.VIX_PROPERTY_JOB_RESULT_GUEST_PROGRAM_ELAPSED_TIME
        )
        if job.pid:
            assert job.pid == props[0], 'job pid has changed'
        job.pid = props[0]
        job.exit_code = props[1]
        job.elapsed_time = props[2]
        _proc_jobs_lock.acquire(True)
        _proc_jobs.pop(job_id)
        _proc_jobs_lock.release()
        job._done_evt.set()
    else:
        raise ValueError(f"Unexpected VIX_EVENTTYPE_JOB ({event_type})")
