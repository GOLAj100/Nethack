import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.vulkan_backend import VulkanBackend
from engine.display import Display
print('Vulkan installed:', VulkanBackend.installed())
backend = VulkanBackend()
devices = backend.enumerate_devices()
print('Vulkan devices:', devices)
if VulkanBackend.installed():
    assert devices
    assert backend.initialize()
    assert backend.available and backend.name in devices
    backend.close()
print('VULKAN DISCOVERY OK')
