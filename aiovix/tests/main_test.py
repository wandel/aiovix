# """
#     vix.tests
#     ---------

#     Tests for the vix library.

#     .. warning:: Unit tests may cause data on running VMs to be lost.
# """

# import os
# import asyncio
# import unittest
# import tempfile

import aiovix
# # from aiovix import VixHost, VixVM, VixSnapshot

import pytest


@pytest.fixture
async def vm():
    host = aiovix.VixHost()
    machine = host.open_vm("D:\\virtual machines\\windows-7-sp1-x64\\windows-7-sp1-x64.vmx")
    snapshot = machine.snapshot_get_named("initial install")
    await machine.snapshot_revert(snapshot)
    await machine.power_on(launch_gui=False)
    
    await machine.wait_for_tools()
    await machine.login('vagrant', 'vagrant')

    yield machine

    if machine.power_state & machine.VIX_POWERSTATE_POWERED_ON:
        await machine.power_off()


@pytest.mark.asyncio
async def test_full(vm: aiovix.VixVM):
    await vm.pause()
    assert vm.power_state & aiovix.VixVM.VIX_POWERSTATE_PAUSED, "vm should  be paused"

    await vm.unpause()
    assert not vm.power_state & aiovix.VixVM.VIX_POWERSTATE_PAUSED, "vm should not be paused"

    await vm.suspend()
    assert vm.power_state & aiovix.VixVM.VIX_POWERSTATE_SUSPENDED, "vm should be suspended"
    
    await vm.power_on()
    assert not vm.power_state & aiovix.VixVM.VIX_POWERSTATE_SUSPENDED, "vm should not be suspeneded"


@pytest.mark.asyncio
async def test_guest_tools(vm: aiovix.VixVM):
    assert 'windows' in vm.guest_os

    assert vm.dir_exists("c:\\temp")


# @pytest.fixture
# def host():
#     conn = aiovix.VixHost()
#     yield conn
#     conn.disconnect()



# @pytest.fixture
# def vm(host):
#     vm = host.find_items()[0]
#     assert isinstance(vm, aiovix.VixVM), "Expected VixVm"
#     yield vm


# def test_host_info(host):
#     host_info = host.host_info

#     assert host_info.host_type in [
#         aiovix.VixHost.VIX_SERVICEPROVIDER_VMWARE_SERVER,
#         aiovix.VixHost.VIX_SERVICEPROVIDER_VMWARE_WORKSTATION,
#         aiovix.VixHost.VIX_SERVICEPROVIDER_VMWARE_PLAYER,
#         aiovix.VixHost.VIX_SERVICEPROVIDER_VMWARE_VI_SERVER,
#         aiovix.VixHost.VIX_SERVICEPROVIDER_VMWARE_WORKSTATION_SHARED,
#     ], 'host_type is unknown'

#     host_info.api_version is not None, 'invalid api_version'
#     assert isinstance(host_info.software_version, str), 'software_version is not a string.'


# def test_find_item_names(host):
#     items = host.find_items(names_only=True)

#     assert isinstance(items, list), 'Expected list'
#     assert len(items) > 0 , 'No VMS running. Cant test...'

#     for item in items:
#         assert isinstance(item, str), 'Expected string'

# def test_find_item_instances(host):
#     items = host.find_items(names_only=False)

#     assert isinstance(items, list), 'Expected list'
#     assert len(items) > 0 , 'No VMS running. Cant test...'

#     for item in items:
#         assert isinstance(item, aiovix.VixVM), 'Expected VixVM'


# def test_properties(vm):
#     assert isinstance(vm.vmx_path, str)
    
#     assert isinstance(vm.machine_info[0], int), 'num CPUs is not an int'
#     assert isinstance(vm.machine_info[1], int), 'memory size is not an int'
#     assert len(vm.machine_info) == 2, 'machine_info must be size 2'
#     assert isinstance(vm.name, str), 'expected str'
#     assert isinstance(vm.guest_os, str), 'expected str'
#     assert isinstance(vm.is_running, bool), 'expected bool'
#     assert isinstance(vm.power_state, int)
#     assert isinstance(vm.tools_state, int)
#     assert isinstance(vm.supported_features, int)

# @pytest.mark.asyncio
# async def test_pause_unpause(vm: aiovix.VixVM):
#     await vm.pause()
#     await vm.unpause()

# @pytest.mark.asyncio
# async def test_poweroff_poweron(vm):
#     vm.power_state & aiovix.VixVM.VIX_POWERSTATE_POWERED_ON > 0, 'expected vm to be powered on'
#     await vm.power_off()
#     vm.power_state & aiovix.VixVM.VIX_POWERSTATE_POWERED_OFF > 0, 'expected vm to be powered off'
#     await vm.power_on()
#     vm.power_state & aiovix.VixVM.VIX_POWERSTATE_POWERED_ON > 0, 'expected vm to be powered on'

# @pytest.mark.asyncio
# async def test_reset(vm):
#     await vm.reset()

# @pytest.mark.asyncio
# async def test_suspend(vm):
#     assert vm.power_state & aiovix.VixVM.VIX_POWERSTATE_POWERED_ON > 0, 'expected vm to be powered on'
#     await vm.suspend()
#     assert vm.power_state & aiovix.VixVM.VIX_POWERSTATE_SUSPENDED > 0, 'expected vm to be suspended'
#     await vm.power_on()
#     assert vm.power_state & aiovix.VixVM.VIX_POWERSTATE_POWERED_ON > 0, 'expected vm to be powered on'


# @pytest.mark.asyncio
# async def test_clone(vm: aiovix.VixVM):
#     snapshot = vm.snapshot_get_current()
#     with tempfile.TemporaryDirectory() as tmpdir:
#         clone_path = os.path.join(tmpdir, "cloned.vmx")
#         cloned_vm = await vm.clone(clone_path, snapshot=snapshot, linked=True)
#         assert isinstance(cloned_vm, aiovix.VixVM)
#         await cloned_vm.vm_delete(delete_files=True)


# @pytest.mark.asyncio
# async def test_snapshot(vm: aiovix.VixVM):
#     assert vm.snapshots_get_root_count() > 0
#     snapshot = vm.snapshot_get_root()
#     await vm.snapshot_revert(snapshot)
#     prev = snapshot.get_num_children()
#     new = await vm.create_snapshot("test_snapshot")
#     assert snapshot.get_num_children() == prev +1
#     vm.snapshot_remove(new)
#     assert snapshot.get_num_children() == prev


# # class VixVMSnapshotTest(BaseVixVMTest):
# #     @pytest.mark.asyncio
# #     async def test_clone_delete(self):
# #         cloned_vm = await vm.clone(r'cloned.vmx', snapshot=vm.snapshot_get_current(), linked=True)
# #         self.assertIsInstance(cloned_vm, VixVM)

# #         await cloned_vm.vm_delete(delete_files=True)

# #     @pytest.mark.asyncio
# #     async def test_create_remove(self):
# #         snapshot = await vm.create_snapshot('Test Snapshot', 'Created By UnitTest', include_memory=False)
# #         self.assertIsInstance(snapshot, VixSnapshot)

# #         self.assertIsInstance(snapshot.name, str)
# #         self.assertIsInstance(snapshot.description, str)
# #         self.assertIsInstance(snapshot.power_state, int)

# #         vm.snapshot_remove(snapshot)


# # class VixSnapshotTest(BaseVixVMTest):
# #     def setUp(self):
# #         super(VixSnapshotTest, self).setUp()

# #         self._snapshot = vm.snapshot_get_current()
# #         self.assertIsInstance(self._snapshot, VixSnapshot)

# #     def test_properties(self):
# #         self.assertIsInstance(self._snapshot.name, str)
# #         self.assertIsInstance(self._snapshot.description, str)
# #         self.assertIsInstance(self._snapshot.power_state, int)

# #     def test_get_named(self):
# #         name = self._snapshot.name

# #         snp = vm.snapshot_get_named(name)
# #         self.assertIsInstance(snp, VixSnapshot)

# #         self.assertEqual(snp.name, name)

# #     def test_root(self):
# #         root = vm.snapshot_get_root()
# #         self.assertIsInstance(root, VixSnapshot)

# #         self.assertIs(root.get_parent(), None)

# #     def test_children(self):
# #         for i in range(self._snapshot.get_num_children()):
# #             self.assertIsInstance(self._snapshot.get_child(i), VixSnapshot)
