# auto_config.py — detecta hardware e retorna perfil recomendado
import os
import platform
import subprocess


def detect_hardware() -> dict:
    cores = os.cpu_count() or 2
    cpu_name = platform.processor() or platform.machine() or "CPU desconhecida"
    ram_gb = 0
    gpu_name = ""
    has_intel_gpu = False
    has_discrete_gpu = False

    # RAM
    try:
        import psutil
        ram_gb = round(psutil.virtual_memory().total / (1024 ** 3))
    except ImportError:
        try:
            if platform.system() == "Windows":
                out = subprocess.run(
                    ["wmic", "ComputerSystem", "get", "TotalPhysicalMemory"],
                    capture_output=True, text=True, timeout=5,
                )
                for line in out.stdout.splitlines():
                    line = line.strip()
                    if line.isdigit():
                        ram_gb = round(int(line) / (1024 ** 3))
                        break
        except Exception:
            pass

    # GPU
    try:
        if platform.system() == "Windows":
            out = subprocess.run(
                ["wmic", "path", "Win32_VideoController", "get", "name"],
                capture_output=True, text=True, timeout=5,
            )
            for line in out.stdout.splitlines():
                line = line.strip()
                if not line or line.lower() == "name":
                    continue
                low = line.lower()
                if "intel" in low and not has_discrete_gpu:
                    has_intel_gpu = True
                    gpu_name = gpu_name or line
                if any(x in low for x in ["nvidia", "geforce", "rtx", "gtx", "quadro", "amd", "radeon", "arc a"]):
                    has_discrete_gpu = True
                    gpu_name = line
        else:
            # Linux — lspci
            out = subprocess.run(["lspci"], capture_output=True, text=True, timeout=5)
            for line in out.stdout.splitlines():
                low = line.lower()
                if "vga" in low or "3d" in low:
                    if "intel" in low:
                        has_intel_gpu = True
                        gpu_name = gpu_name or line.split(":")[-1].strip()
                    if any(x in low for x in ["nvidia", "amd", "radeon"]):
                        has_discrete_gpu = True
                        gpu_name = line.split(":")[-1].strip()
    except Exception:
        pass

    # Perfil
    if has_discrete_gpu or cores >= 16:
        profile = "high"
    elif cores >= 8:
        profile = "medium"
    else:
        profile = "low"

    recommended = {
        "low": {
            "WEBCAM_WIDTH": 320, "WEBCAM_HEIGHT": 180,
            "INPUT_SIZE": 320, "FRAME_SKIP": 8,
            "STREAM_FPS": 12, "TORCH_THREADS": 1,
        },
        "medium": {
            "WEBCAM_WIDTH": 640, "WEBCAM_HEIGHT": 480,
            "INPUT_SIZE": 320, "FRAME_SKIP": 4,
            "STREAM_FPS": 20, "TORCH_THREADS": 2,
        },
        "high": {
            "WEBCAM_WIDTH": 1280, "WEBCAM_HEIGHT": 720,
            "INPUT_SIZE": 416, "FRAME_SKIP": 2,
            "STREAM_FPS": 30, "TORCH_THREADS": 4,
        },
    }[profile]

    parts = [cpu_name]
    if ram_gb:
        parts.append(f"{ram_gb} GB RAM")
    if gpu_name:
        parts.append(gpu_name)
    hardware_str = "  |  ".join(parts)

    return {
        "profile":          profile,
        "cores":            cores,
        "ram_gb":           ram_gb,
        "cpu_name":         cpu_name,
        "gpu_name":         gpu_name,
        "has_intel_gpu":    has_intel_gpu,
        "has_discrete_gpu": has_discrete_gpu,
        "hardware_str":     hardware_str,
        "recommended":      recommended,
    }


if __name__ == "__main__":
    import json
    info = detect_hardware()
    print(json.dumps(info, indent=2, ensure_ascii=False))
