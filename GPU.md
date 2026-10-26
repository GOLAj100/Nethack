# GPU backend (experimental)

Install optional dependency: `python -m pip install -r requirements-gpu.txt`.
F2 → Graphics → **GPU output** toggles software/OpenGL.

The same setting now has **Vulkan**. Vulkan currently initializes the real
instance and selects the requested physical device, then uses the proven
OpenGL presentation as a safe swapchain bridge. This is intentional: device
discovery and ownership are in place before replacing the SDL/WGL presentation
path with a Vulkan surface/swapchain. The game reports this transitional state
instead of claiming that Vulkan is rendering frames when it is not.

OpenGL performs first-person terrain traversal in GLSL (including vertical
pitch, floors, ceilings and shafts), GPU billboard sprites with depth testing,
and scales/presents the canvas on GPU. The volumetric 3D board uses a cached
GPU mesh and hardware depth buffer. UI remains CPU-rendered. Picking and
diagnostics may read one depth pixel, but normal frames do not read the terrain
depth buffer back to the CPU. This is a hybrid backend, not a complete UI port.
GPU shader failure falls back to CPU rays and logs
the reason in the game journal. OpenGL window failure uses software output.

## Choosing a GPU on Windows

The Graphics menu entry **GPU: Windows graphics settings** opens the OS page.
Add the Python executable used to launch this game (find it with
`python -c "import sys; print(sys.executable)"`). Under Options choose the
available GPU / High performance and restart the game. Windows/driver
determines the adapters offered; this renderer cannot switch a live WGL
context to an arbitrary numbered adapter. The journal reports the actual
OpenGL renderer after enabling GPU output. No fictitious adapter selector
is provided.

The **Vulkan device: enumerate** menu entry lists physical devices found by
the Vulkan loader. The current RTX 4060 Ti is detected as
`NVIDIA GeForce RTX 4060 Ti`.

## Benchmark

`python tests/gpu_benchmark.py` creates real windows and compares CPU and GPU
with the same scene and rotating first-person camera. Also measures ASCII
and compares selected CPU/GPU ray depths. It uses temporary save/settings.
Do not use SDL dummy for this benchmark.

Measured RTX 4060 Ti, 1280×720, high ray quality: ~102 ms CPU vs ~8 ms hybrid
GPU; ASCII ~11 ms software vs ~12 ms OpenGL. A full 3D board with outlines was
~110 ms CPU vs ~6 ms GPU in the test scene. These include update/render/
presentation, exclude the game's 60-FPS limiter, and are scene-dependent.
