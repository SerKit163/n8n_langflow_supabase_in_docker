"""
Модуль определения железа системы
"""
import platform
import subprocess
from typing import Dict, Optional, List
import psutil


def detect_hardware() -> Dict:
    """
    Определяет характеристики системы:
    - CPU (ядра, частота)
    - RAM (общий объем, доступный)
    - GPU (NVIDIA/AMD/Intel, память, CUDA)
    - Диск (свободное место)
    - Тип системы (VPS/локальный ПК)
    """
    hardware = {
        'cpu': detect_cpu(),
        'ram': detect_ram(),
        'gpu': detect_gpu(),
        'disk': detect_disk(),
        'system_type': detect_system_type(),
        'os': platform.system(),
        'os_version': platform.version()
    }
    
    return hardware


def detect_cpu() -> Dict:
    """Определяет характеристики CPU"""
    cpu_count = psutil.cpu_count(logical=False)  # Физические ядра
    cpu_count_logical = psutil.cpu_count(logical=True)  # Логические ядра
    
    # Получаем частоту CPU
    cpu_freq = psutil.cpu_freq()
    frequency = cpu_freq.current if cpu_freq else 0
    
    return {
        'cores': cpu_count or 1,
        'threads': cpu_count_logical or cpu_count or 1,
        'frequency_ghz': round(frequency / 1000, 2) if frequency else 0,
        'model': get_cpu_model()
    }


def get_cpu_model() -> str:
    """Получает модель CPU"""
    try:
        if platform.system() == "Windows":
            return platform.processor()
        elif platform.system() == "Linux":
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if 'model name' in line:
                        return line.split(':')[1].strip()
        elif platform.system() == "Darwin":
            return subprocess.check_output(['sysctl', '-n', 'machdep.cpu.brand_string']).decode().strip()
    except Exception:
        pass
    return "Unknown CPU"


def detect_ram() -> Dict:
    """Определяет характеристики RAM"""
    mem = psutil.virtual_memory()
    return {
        'total_gb': round(mem.total / (1024**3), 2),
        'available_gb': round(mem.available / (1024**3), 2),
        'used_gb': round(mem.used / (1024**3), 2),
        'percent': mem.percent
    }


def detect_gpu() -> Dict:
    """Определяет наличие и характеристики GPU"""
    gpu_info = {
        'available': False,
        'vendor': None,
        'model': None,
        'memory_gb': 0,
        'cuda_available': False,
        'devices': []
    }
    
    # Проверяем NVIDIA GPU
    nvidia_gpu = detect_nvidia_gpu()
    if nvidia_gpu:
        gpu_info.update(nvidia_gpu)
        return gpu_info
    
    # Проверяем AMD GPU (через rocm-smi если доступен)
    amd_gpu = detect_amd_gpu()
    if amd_gpu:
        gpu_info.update(amd_gpu)
        return gpu_info
    
    # Проверяем Intel GPU
    intel_gpu = detect_intel_gpu()
    if intel_gpu:
        gpu_info.update(intel_gpu)
        return gpu_info
    
    return gpu_info


def detect_nvidia_gpu() -> Optional[Dict]:
    """Определяет NVIDIA GPU через nvidia-smi или pynvml"""
    try:
        # Пробуем через nvidia-smi
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            devices = []
            for line in lines:
                if line:
                    parts = line.split(',')
                    if len(parts) >= 2:
                        model = parts[0].strip()
                        memory_str = parts[1].strip()
                        # Парсим память (например "12288 MiB")
                        memory_mb = int(memory_str.split()[0])
                        memory_gb = round(memory_mb / 1024, 2)
                        devices.append({
                            'model': model,
                            'memory_gb': memory_gb
                        })
            
            if devices:
                return {
                    'available': True,
                    'vendor': 'NVIDIA',
                    'model': devices[0]['model'],
                    'memory_gb': devices[0]['memory_gb'],
                    'cuda_available': True,
                    'devices': devices
                }
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass
    
    # Пробуем через pynvml
    try:
        import pynvml
        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()
        
        if device_count > 0:
            devices = []
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(handle).decode('utf-8')
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                memory_gb = round(mem_info.total / (1024**3), 2)
                devices.append({
                    'model': name,
                    'memory_gb': memory_gb
                })
            
            if devices:
                return {
                    'available': True,
                    'vendor': 'NVIDIA',
                    'model': devices[0]['model'],
                    'memory_gb': devices[0]['memory_gb'],
                    'cuda_available': True,
                    'devices': devices
                }
    except Exception:
        pass
    
    return None


def detect_amd_gpu() -> Optional[Dict]:
    """Определяет AMD GPU через rocm-smi"""
    try:
        result = subprocess.run(
            ['rocm-smi', '--showid'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return {
                'available': True,
                'vendor': 'AMD',
                'model': 'AMD GPU',
                'memory_gb': 0,  # Нужно парсить отдельно
                'cuda_available': False,
                'devices': []
            }
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass
    
    return None


def detect_intel_gpu() -> Optional[Dict]:
    """Определяет Intel GPU"""
    try:
        if platform.system() == "Linux":
            # Проверяем через lspci
            result = subprocess.run(
                ['lspci'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and 'Intel' in result.stdout and 'VGA' in result.stdout:
                return {
                    'available': True,
                    'vendor': 'Intel',
                    'model': 'Intel GPU',
                    'memory_gb': 0,
                    'cuda_available': False,
                    'devices': []
                }
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass
    
    return None


def detect_disk() -> Dict:
    """Определяет свободное место на диске"""
    disk = psutil.disk_usage('/')
    return {
        'total_gb': round(disk.total / (1024**3), 2),
        'free_gb': round(disk.free / (1024**3), 2),
        'used_gb': round(disk.used / (1024**3), 2),
        'percent': disk.percent
    }


def detect_system_type() -> str:
    """
    Определяет тип системы: VPS или локальный ПК
    """
    # Признаки VPS:
    # - Обычно в Docker контейнере или виртуальной машине
    # - Может быть systemd или другие признаки
    
    try:
        # Проверяем через systemd
        if platform.system() == "Linux":
            # Проверяем наличие systemd
            result = subprocess.run(
                ['systemd-detect-virt'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                virt_type = result.stdout.strip()
                if virt_type and virt_type != 'none':
                    return 'vps'
        
        # Проверяем через /proc/1/cgroup (Docker контейнер)
        try:
            with open('/proc/1/cgroup', 'r') as f:
                content = f.read()
                if 'docker' in content or 'lxc' in content:
                    return 'vps'
        except Exception:
            pass
        
        # Проверяем через dmidecode (если доступен)
        try:
            result = subprocess.run(
                ['dmidecode', '-s', 'system-product-name'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                product = result.stdout.strip().lower()
                if any(keyword in product for keyword in ['vps', 'cloud', 'vmware', 'virtualbox', 'kvm', 'xen']):
                    return 'vps'
        except Exception:
            pass
        
    except Exception:
        pass
    
    # По умолчанию считаем локальным ПК
    return 'local'


def get_gpu_devices() -> List[Dict]:
    """Возвращает список GPU устройств"""
    gpu = detect_gpu()
    return gpu.get('devices', [])

