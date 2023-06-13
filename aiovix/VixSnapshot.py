from .VixHandle import VixHandle
from .VixError import VixError
from aiovix import _backend
vix = _backend._vix
ffi = _backend._ffi


class VixSnapshot(VixHandle):
    """Represents a VM's snapshot"""

    def __init__(self, handle):
        super(VixSnapshot, self).__init__(handle)
        assert self.get_type() == VixHandle.VIX_HANDLETYPE_SNAPSHOT, 'Expected VixSnapshot handle.'

    @property
    def name(self):
        """Gets the snapshot's name.

        :rtype: str
        """

        return self.get_properties(VixHandle.VIX_PROPERTY_SNAPSHOT_DISPLAYNAME)

    @property
    def description(self):
        """Get the snapshot's description.

        :rtype: str
        """
        return self.get_properties(VixHandle.VIX_PROPERTY_SNAPSHOT_DESCRIPTION)
    
    @property
    def power_state(self):
        """Gets the snapshot's power state.
        
        :returns: Power state, can be a combination of VixVM.VIX_VM_POWERSTATE_*
        :rtype: int
        """

        return self.get_properties(VixHandle.VIX_PROPERTY_SNAPSHOT_POWERSTATE)

    def get_num_children(self):
        """Gets the number of children the current snapshot has.

        :raises vix.VixError: On failure to get child count.
        """

        child_count = ffi.new('int*')
        error_code = vix.VixSnapshot_GetNumChildren(
            self._handle,
            child_count,
        )

        if error_code != VixError.VIX_OK:
            raise VixError(error_code)

        return int(child_count[0])

    def get_child(self, child_index):
        """Gets a child snapshot at the designated index

        :param int child_index: Index of child snapshot.

        :returns: Snapshot at specified index.
        :rtype: .VixSnapshot

        :raises vix.VixError: On failure to retrieve snapshot.
        """

        child_handle = ffi.new('VixHandle*')
        error_code = vix.VixSnapshot_GetChild(
            self._handle,
            child_index,
            child_handle,
        )

        if error_code != VixError.VIX_OK:
            raise VixError(error_code)

        return VixSnapshot(child_handle[0])

    def get_parent(self):
        """Gets the parent of the current snapshot.

        :returns: Parent of current snapshot or None if snapshot is a root.
        :rtype: .VixSnapshot

        :raises vix.VixError: On failure to get snapshot.
        """
        
        parent_handle = ffi.new('VixHandle*')
        error_code = vix.VixSnapshot_GetParent(
            self._handle,
            parent_handle,
        )

        if error_code != VixError.VIX_OK:
            raise VixError(error_code)

        temp_handle = VixHandle(parent_handle[0])
        if temp_handle.get_type() == VixHandle.VIX_HANDLETYPE_NONE:
            temp_handle.release()
            return None

        return VixSnapshot(parent_handle[0])
