"""Named Windows integrations. Never execute model-generated shell scripts."""
from __future__ import annotations

import json
import os
from pathlib import Path
import platform as host
import shutil
import subprocess
import tempfile
import threading
import time
from urllib.parse import quote


class ApplicationNotFound(FileNotFoundError):
    def __init__(self, name):
        self.name = str(name)[:120]
        super().__init__(f"{self.name} ilovasi o'rnatilgan katalogda topilmadi. Microsoft Store'dan qidirish mumkin; o'rnatish faqat sizning tanlovingiz bilan.")


def windows():
    if os.name != 'nt':
        raise OSError('Bu imkoniyat Windows uchun.')


def powershell(script):
    windows()
    binary = Path(os.environ.get('SystemRoot', r'C:\Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
    result = subprocess.run([str(binary), '-NoProfile', '-NonInteractive', '-Command', script],
                            capture_output=True, encoding='utf-8', errors='replace', timeout=12,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise OSError('Windows ma’lumotini o‘qib bo‘lmadi (ruxsat yoki komponent mavjud emas).')
    return result.stdout.lstrip('\ufeff').strip()


def system_exe(name):
    return Path(os.environ.get('SystemRoot', r'C:\Windows'))/'System32'/name


def open_file(path):
    windows()
    from .files import TEXT_TYPES
    if path.is_dir():
        os.startfile(str(path))
    elif path.suffix.casefold() in TEXT_TYPES:
        subprocess.Popen([str(system_exe('notepad.exe')), str(path)], shell=False)
    elif path.suffix.casefold() in {'.docx', '.xlsx', '.pptx', '.pdf', '.png', '.jpg', '.jpeg', '.webp', '.bmp', '.mp3', '.wav', '.mp4', '.ogg', '.flac'}:
        os.startfile(str(path))
    else:
        raise ValueError('Bu fayl turi avtomatik bajarilmaydi. Skript, EXE, yorliq va makroli hujjatlarni ochish yopiq.')
    return 'Ochish so‘rovi yuborildi: '+str(path)


def reveal_file(path):
    windows()
    binary = Path(os.environ.get('SystemRoot', r'C:\Windows'))/'explorer.exe'
    subprocess.Popen([str(binary), '/select,', str(path)], shell=False)
    return 'Explorer’da ko‘rsatish so‘rovi yuborildi: '+str(path)


ALIASES = {'bloknot': 'notepad', 'kalkulyator': 'calculator', 'calc': 'calculator',
           'fayl menejeri': 'explorer', 'sozlamalar': 'settings', 'power point': 'powerpoint',
           'microsoft word': 'word', 'microsoft excel': 'excel', 'google chrome': 'chrome', 'ms-settings:': 'settings'}


class PlatformEngine:
    def __init__(self):
        self._apps = []
        self._loaded = 0.
        self._lock = threading.RLock()

    def apps(self):
        windows()
        with self._lock:
            if self._loaded and time.monotonic()-self._loaded < 120:
                return list(self._apps)
            apps = {'settings': {'name': 'Settings', 'path': 'ms-settings:'}}
            for name, binary in [('Notepad', system_exe('notepad.exe')), ('Calculator', system_exe('calc.exe')),
                                 ('Explorer', Path(os.environ.get('SystemRoot', r'C:\Windows'))/'explorer.exe')]:
                if binary.is_file():
                    apps[name.casefold()] = {'name': name, 'path': str(binary)}
            import winreg
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                    try:
                        with winreg.OpenKey(hive, r'Software\Microsoft\Windows\CurrentVersion\App Paths', 0, winreg.KEY_READ | view) as root:
                            for i in range(min(winreg.QueryInfoKey(root)[0], 1500)):
                                name = winreg.EnumKey(root, i)
                                try:
                                    with winreg.OpenKey(root, name) as key:
                                        value = Path(os.path.expandvars(winreg.QueryValue(key, None).strip('"')))
                                        if value.is_absolute() and value.is_file() and value.suffix.casefold() == '.exe':
                                            title = Path(name).stem
                                            apps[title.casefold()] = {'name': title, 'path': str(value)}
                                except OSError:
                                    continue
                    except OSError:
                        continue
            # Read shortcuts only; ignore argument-bearing or script shortcuts.
            try:
                import pythoncom
                import win32com.client
                pythoncom.CoInitialize()
                try:
                    shell = win32com.client.Dispatch('WScript.Shell')
                    starts = [Path(os.environ.get('ProgramData', r'C:\ProgramData'))/'Microsoft/Windows/Start Menu/Programs',
                              Path(os.environ.get('APPDATA', ''))/'Microsoft/Windows/Start Menu/Programs']
                    deadline = time.monotonic()+4
                    count = 0
                    for start in starts:
                        for folder, dirs, files in os.walk(start, followlinks=False):
                            dirs[:] = [name for name in dirs if not (Path(folder)/name).is_symlink()]
                            if time.monotonic() > deadline or count > 1500:
                                break
                            for name in files:
                                count += 1
                                if not name.casefold().endswith('.lnk'):
                                    continue
                                try:
                                    link = shell.CreateShortcut(str(Path(folder)/name))
                                    target = Path(link.TargetPath)
                                    if target.is_absolute() and target.is_file() and target.suffix.casefold() == '.exe' and not link.Arguments:
                                        title = Path(name).stem
                                        apps[title.casefold()] = {'name': title, 'path': str(target)}
                                except Exception:
                                    continue
                finally:
                    pythoncom.CoUninitialize()
            except Exception:
                # COM/Start Menu can be unavailable under organizational policy.
                # Keep the verified built-ins and registry catalog usable.
                pass
            self._apps = sorted(apps.values(), key=lambda item: item['name'].casefold())
            self._loaded = time.monotonic()
            return list(self._apps)

    def find(self, name):
        query = name.casefold().strip().removesuffix('.exe')
        query = ALIASES.get(query, query)
        if not query or len(query) > 120 or any(c in query for c in '\r\n;|<>'):
            raise ValueError('Faqat ilova nomini yozing, buyruq/argument emas.')
        apps = self.apps()
        exact = [item for item in apps if item['name'].casefold() == query or Path(item['path']).stem.casefold() == query]
        matches = exact or [item for item in apps if query in item['name'].casefold()]
        # Several shortcuts can point at the same executable.
        return list({item['path'].casefold(): item for item in matches}.values())

    def resolve(self, name):
        query = name.casefold().strip().removesuffix('.exe')
        query = ALIASES.get(query, query)
        # Preserve the previous automatic built-ins without letting a similarly
        # named registry entry/shortcut replace a trusted Windows executable.
        if query in {'notepad', 'calculator', 'explorer', 'settings'}:
            windows()
            if query == 'settings':
                return {'name': 'Settings', 'path': 'ms-settings:'}
            binary = (Path(os.environ.get('SystemRoot', r'C:\Windows'))/'explorer.exe' if query == 'explorer'
                      else system_exe('notepad.exe' if query == 'notepad' else 'calc.exe'))
            if not binary.is_file():
                raise ApplicationNotFound(name)
            return {'name': query.title(), 'path': str(binary)}
        matches = self.find(name)
        if not matches:
            raise ApplicationNotFound(name)
        if len(matches) > 1:
            raise ValueError('Bir nechta ilova topildi. Aniq nomini tanlang: '+', '.join(item['name'] for item in matches[:12]))
        return matches[0]

    def open_app(self, name):
        app = self.resolve(name)
        if app['path'] == 'ms-settings:':
            os.startfile(app['path'])
        else:
            subprocess.Popen([app['path']], shell=False)
        return 'Ilovani ochish so‘rovi yuborildi: '+app['name']

    def execute(self, key, args):
        if key in {'app_find', 'app_inventory', 'app_open', 'app_shortcut'}:
            if key == 'app_find':
                return {'matches': self.find(args['name']), 'note': 'App Paths va argumentsiz Start Menu yorliqlari; barcha Store paketlari katalogi emas.'}
            if key == 'app_inventory':
                return {'apps': self.apps()[:300], 'bounded': True}
            if key == 'app_open':
                return self.open_app(args['name'])
            app = self.resolve(args['name'])
            if app['path'] == 'ms-settings:':
                raise ValueError('Bu tizim URI uchun EXE yorlig‘i yaratilmaydi.')
            from .files import valid_name
            from jarvis.office.destinations import desktop_directory
            name = app['name']+'.lnk'
            valid_name(name)
            output = desktop_directory()/name
            if output.exists():
                raise ValueError('Bu nomli yorliq allaqachon mavjud.')
            import pythoncom
            import win32com.client
            pythoncom.CoInitialize()
            try:
                with tempfile.TemporaryDirectory(prefix='jarvis-shortcut-') as temporary:
                    draft = Path(temporary)/name
                    link = win32com.client.Dispatch('WScript.Shell').CreateShortcut(str(draft))
                    link.TargetPath = app['path']
                    link.WorkingDirectory = str(Path(app['path']).parent)
                    link.Save()
                    with draft.open('rb') as source, output.open('xb') as target:
                        shutil.copyfileobj(source, target)
            finally:
                pythoncom.CoUninitialize()
            return 'Yangi Desktop yorlig‘i: '+str(output)
        if key == 'store_search':
            windows()
            name = args['name'].strip()
            if len(name) > 120:
                raise ValueError('Ilova nomi 120 belgigacha.')
            os.startfile('ms-windows-store://search/?query='+quote(name, safe=''))
            return 'Store qidiruvi ochildi. O‘rnatishni o‘zingiz tanlaysiz; avtomatik yuklanmadi.'
        if key == 'mrt_open':
            windows()
            binary = system_exe('MRT.exe')
            if not binary.is_file():
                raise FileNotFoundError('Windows MRT.exe topilmadi. Windows Update yoki Microsoft Support orqali tekshiring.')
            # No unattended removal switches, UAC acceptance, or security UI automation.
            os.startfile(str(binary))
            return 'MRT oynasini ochish so‘rovi yuborildi. UAC va skan rejimini o‘zingiz tanlang. Tekshiruv natijasi hali noma’lum; MRT to‘liq antivirus emas.'
        if key == 'mrt_report':
            windows()
            path = Path(os.environ.get('SystemRoot', r'C:\Windows'))/'debug/mrt.log'
            if not path.is_file():
                return 'MRT jurnali topilmadi; bu virus yo‘qligini anglatmaydi.'
            with path.open('rb') as stream:
                stream.seek(max(0, path.stat().st_size-30000))
                raw = stream.read(30000)
            text = raw.decode('utf-16-le' if b'\x00' in raw[:100] else 'utf-8', errors='replace')
            return {'modified': path.stat().st_mtime, 'log_tail': text[-12000:], 'note': 'Mavjud, ehtimol eski jurnal. Bu hozirgi skan yakunlandi degani emas.'}
        if key == 'security_status':
            text = powershell("[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; Get-MpComputerStatus | Select-Object AntivirusEnabled,RealTimeProtectionEnabled,AntispywareEnabled,AntivirusSignatureLastUpdated,QuickScanEndTime,FullScanEndTime | ConvertTo-Json -Compress")
            return {'defender': json.loads(text), 'note': 'Faqat holat o‘qildi; sozlama o‘zgarmadi, toza kompyuter kafolati emas.'}
        if key in {'system_info', 'disk_info', 'process_list', 'battery_info', 'network_info'}:
            import psutil
            if key == 'system_info':
                memory = psutil.virtual_memory()
                return {'os': host.platform(), 'machine': host.machine(), 'logical_cpus': psutil.cpu_count(), 'ram_bytes': memory.total, 'ram_percent': memory.percent, 'boot_time': psutil.boot_time()}
            if key == 'disk_info':
                result = []
                for disk in psutil.disk_partitions():
                    if 'cdrom' in disk.opts or not disk.fstype:
                        continue
                    try:
                        usage = psutil.disk_usage(disk.mountpoint)
                        result.append({'disk': disk.mountpoint, 'free': usage.free, 'total': usage.total, 'percent': usage.percent})
                    except OSError:
                        pass
                return result
            if key == 'process_list':
                result = []
                for process in psutil.process_iter(['pid', 'name', 'memory_info']):
                    try:
                        info = process.info
                        result.append({'pid': info['pid'], 'name': info['name'], 'ram_bytes': info['memory_info'].rss if info['memory_info'] else 0})
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                return sorted(result, key=lambda item: item['ram_bytes'], reverse=True)[:80]
            if key == 'battery_info':
                battery = psutil.sensors_battery()
                return {'available': False} if battery is None else {'available': True, 'percent': battery.percent, 'plugged': battery.power_plugged, 'seconds_left': battery.secsleft}
            addresses = psutil.net_if_addrs()
            states = psutil.net_if_stats()
            return [{'name': name, 'up': states[name].isup if name in states else None,
                     'addresses': [address.address for address in values]} for name, values in addresses.items()][:40]
        if key == 'clipboard_format':
            import pyperclip
            mode = args['mode'].casefold().strip()
            if mode not in {'trim', 'sort', 'unique'}:
                raise ValueError('mode: trim, sort yoki unique.')
            original = pyperclip.paste()
            if len(original) > 500000:
                raise ValueError('Clipboard matni juda katta (500000 belgi).')
            lines = original.splitlines()
            result = '\n'.join(line.strip() for line in lines) if mode == 'trim' else '\n'.join(sorted(lines, key=str.casefold) if mode == 'sort' else dict.fromkeys(lines))
            if pyperclip.paste() != original:
                raise ValueError('Clipboard tashqaridan o‘zgardi; amal bekor qilindi.')
            pyperclip.copy(result)
            return f'Clipboard {mode} bilan yangilandi: {len(lines)} qator. Matn AI yoki task tarixiga yuborilmadi.'
        raise ValueError('Noma’lum Windows qobiliyati: '+key)


applications = PlatformEngine()
