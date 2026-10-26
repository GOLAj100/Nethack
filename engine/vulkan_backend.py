"""Vulkan device discovery/ownership for the optional rendering backend.

The game keeps its SDL canvas contract while Vulkan is introduced in stages:
this module creates a real Vulkan instance and selects a physical device. The
current raster presentation remains OpenGL/CPU until a platform swapchain is
available; no fake "Vulkan FPS" is reported.
"""
from __future__ import annotations

try:
    import vulkan as vk
except ImportError:  # optional dependency
    vk = None


class VulkanBackend:
    def __init__(self, preferred="auto"):
        self.preferred = preferred or "auto"
        self.instance = None
        self.device = None
        self.name = "Vulkan unavailable"
        self.error = ""
        self.available = False

    @staticmethod
    def installed():
        return vk is not None

    @staticmethod
    def _name(properties):
        value = properties.deviceName
        return value.decode(errors="replace") if isinstance(value, bytes) else str(value)

    def initialize(self):
        if vk is None:
            self.error = "Install vulkan package and a Vulkan driver"
            return False
        try:
            info = vk.VkInstanceCreateInfo(
                sType=vk.VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
                pApplicationInfo=vk.VkApplicationInfo(
                    sType=vk.VK_STRUCTURE_TYPE_APPLICATION_INFO,
                    pApplicationName="NET HACK",
                    applicationVersion=1,
                    pEngineName="NET HACK",
                    engineVersion=1,
                    apiVersion=vk.VK_API_VERSION_1_0))
            self.instance = vk.vkCreateInstance(info, None)
            devices = vk.vkEnumeratePhysicalDevices(self.instance)
            if not devices:
                raise RuntimeError("Vulkan reports no physical devices")
            props = [vk.vkGetPhysicalDeviceProperties(d) for d in devices]
            selected = 0
            if self.preferred not in ("auto", "primary", "high-performance"):
                for i, prop in enumerate(props):
                    if prop.deviceName.decode(errors="replace") == self.preferred:
                        selected = i
                        break
            elif self.preferred == "high-performance":
                selected = max(range(len(props)), key=lambda i: props[i].deviceType)
            self.device = devices[selected]
            self.name = self._name(props[selected])
            self.available = True
            return True
        except Exception as exc:  # Vulkan remains optional and non-fatal.
            self.error = str(exc)
            self.close()
            return False

    def enumerate_devices(self):
        if vk is None:
            return []
        temp = VulkanBackend()
        if not temp.initialize():
            return []
        try:
            return [temp._name(vk.vkGetPhysicalDeviceProperties(d))
                    for d in vk.vkEnumeratePhysicalDevices(temp.instance)]
        finally:
            temp.close()

    def close(self):
        if self.instance is not None and vk is not None:
            try:
                vk.vkDestroyInstance(self.instance, None)
            except Exception:
                pass
        self.instance = None
        self.device = None
        self.available = False
