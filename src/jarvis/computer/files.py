"""Scoped file index, explicit edits with backups, and bounded archive operations."""
from __future__ import annotations

import csv
from contextlib import contextmanager
import difflib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import stat
from itertools import islice
import tempfile
import threading
import time
import uuid
import zipfile

TEXT_TYPES = {".txt", ".md", ".csv", ".json", ".log", ".py", ".js", ".ts", ".html", ".css", ".xml", ".yaml", ".yml", ".ini"}
BLOCKED_PARTS = {".git", ".venv", "node_modules", "__pycache__", "appdata", "windows", "program files", "program files (x86)", ".ssh", ".aws", ".codex", ".agents"}
BLOCKED_NAMES = {".env", "connections.json", "voice.json", "credentials.json", "id_rsa", "id_ed25519"}
SECRET_TYPES = {'.pem', '.key', '.pfx', '.p12'}
MAX_FILE = 100*1024*1024
MAX_TOTAL = 300*1024*1024
MAX_ENTRIES = 10000


def valid_name(name):
    base = name.split('.')[0].upper().rstrip(' ')
    if (not name or name in {'.', '..'} or name.rstrip(' .') != name
            or any(ord(c) < 32 or c in '/\\:*?"<>|' for c in name)
            or base in {'CON', 'PRN', 'AUX', 'NUL'}
            or base in {f'{prefix}{number}' for prefix in ('COM', 'LPT') for number in range(1, 10)}):
        raise ValueError("Windows uchun xavfsiz oddiy fayl nomi kerak.")


def linked(path):
    return path.is_symlink() or (path.exists() and bool(getattr(path.stat(), 'st_file_attributes', 0) & 0x400))


def default_roots():
    home = Path.home()
    roots = [Path.cwd()]
    roots += [home/name for name in ("Desktop", "Documents", "Downloads", "Pictures", "Music", "Videos")]
    try:
        from jarvis.office.destinations import desktop_directory
        roots.append(desktop_directory())
    except (OSError, ValueError):
        pass
    return roots


class FileScope:
    def __init__(self, roots, storage):
        candidates = sorted({Path(path).resolve() for path in roots if Path(path).is_dir()}, key=lambda p: len(p.parts))
        self.roots = []
        for path in candidates:
            if not any(path.is_relative_to(root) for root in self.roots):
                self.roots.append(path)
        self.storage = Path(storage).resolve()
        self.private = (Path.cwd()/'data').resolve()

    def allowed(self, path):
        path = Path(path)
        if any(part.casefold() in BLOCKED_PARTS or part.casefold().startswith(".env") for part in path.parts):
            return False
        if path.name.casefold() in BLOCKED_NAMES or path.suffix.casefold() in SECRET_TYPES:
            return False
        try:
            resolved = path.resolve()
        except (OSError, RuntimeError):
            return False
        if resolved.is_relative_to(self.storage) or resolved.is_relative_to(self.private):
            return False
        try:
            for part in path.parts[1:] if path.anchor else path.parts:
                valid_name(part)
        except ValueError:
            return False
        if resolved != path.absolute() and any(part.casefold() in BLOCKED_PARTS for part in resolved.parts):
            return False
        return any(resolved.is_relative_to(root) for root in self.roots)

    def path(self, value, *, exists=True, mutate=False):
        path = Path(value)
        if not path.is_absolute() or not self.allowed(path):
            raise ValueError("Yo'l ruxsat etilgan lokal papkalarda bo'lishi kerak; maxfiy/tizim yo'llari yopiq.")
        for part in (path, *path.parents):
            if linked(part):
                raise ValueError("Symlink/junction orqali fayl amali bajarilmaydi.")
        if mutate:
            valid_name(path.name)
        path = path.resolve(strict=exists)
        if mutate and (path in self.roots or any(root.is_relative_to(path) for root in self.roots)):
            raise ValueError("Ruxsat ildizi yoki uning ota papkasi o'zgartirilmaydi.")
        return path

    def walk(self, root=None, *, seconds=8., limit=MAX_ENTRIES):
        roots = [self.path(root)] if root else self.roots
        deadline = time.monotonic()+seconds
        count = 0
        for start in roots:
            for folder, dirs, files in os.walk(start, followlinks=False):
                if time.monotonic() > deadline:
                    return
                safe = []
                for name in dirs:
                    try:
                        if not name.startswith('.') and self.allowed(Path(folder)/name) and not linked(Path(folder)/name):
                            safe.append(name)
                    except OSError:
                        pass
                dirs[:] = safe
                for name in files:
                    if count >= limit or time.monotonic() > deadline:
                        return
                    path = Path(folder)/name
                    if name.startswith(".") or not self.allowed(path):
                        continue
                    try:
                        if path.is_file() and not linked(path):
                            count += 1
                            yield path
                    except OSError:
                        continue


class FileIndex:
    def __init__(self, scope, storage):
        self.scope = scope
        self.database = Path(storage)/"index.db"
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.last = 0.
        self.scanned = {}
        with self.connect() as database:
            database.execute("CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY,name TEXT,size INTEGER,mtime REAL)")

    @contextmanager
    def connect(self):
        database = sqlite3.connect(self.database, timeout=15)
        try:
            with database:
                yield database
        finally:
            database.close()

    def refresh(self, force=False, root=None):
        with self.lock:
            if root:
                root = self.scope.path(root)
                if not root.is_dir():
                    raise ValueError('Qidirish uchun papka tanlang.')
            key = str(root).casefold() if root else ''
            if self.last == 0:
                self.scanned.clear()
            if not force and time.monotonic()-self.scanned.get(key, 0) < 60:
                return
            rows = []
            for path in self.scope.walk(root, limit=50000):
                try:
                    info = path.stat()
                    rows.append((str(path), path.name.casefold(), info.st_size, info.st_mtime))
                except OSError:
                    pass
            with self.connect() as database:
                if root:
                    prefix = (str(root)+os.sep).replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
                    database.execute("DELETE FROM files WHERE path LIKE ? ESCAPE '\\'", (prefix+'%',))
                else:
                    database.execute("DELETE FROM files")
                    self.scanned.clear()
                database.executemany("INSERT OR REPLACE INTO files VALUES(?,?,?,?)", rows)
            self.last = time.monotonic()
            self.scanned[key] = self.last

    def rows(self, query="", root=None, order="name", limit=100):
        if root:
            root = self.scope.path(root)
        self.refresh(root=root)
        order = {"name": "name", "size": "size DESC", "mtime": "mtime DESC"}[order]
        escaped = query.casefold().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        with self.connect() as database:
            rows = database.execute(f"SELECT path,size,mtime FROM files WHERE name LIKE ? ESCAPE '\\' ORDER BY {order}", ("%"+escaped+"%",)).fetchall()
        result = []
        for value, size, mtime in rows:
            path = Path(value)
            if (not root or path.is_relative_to(root)) and self.scope.allowed(path) and path.is_file():
                result.append({"path": str(path), "size": size, "modified": mtime})
                if len(result) >= limit:
                    break
        return result


def checksum(path):
    if path.stat().st_size > MAX_FILE:
        raise ValueError("Hash/taqqoslash uchun fayl 100 MB dan katta.")
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            total += len(block)
            if total > MAX_FILE:
                raise ValueError('Hash vaqtida fayl 100 MB chegarasidan oshdi.')
            digest.update(block)
    return digest.hexdigest()


def bounded_copy(source, output, limit=MAX_FILE):
    total = 0
    for block in iter(lambda: source.read(1024*1024), b''):
        total += len(block)
        if total > limit:
            raise ValueError('Nusxalashda xavfsiz hajm chegarasi oshdi; natija qisman yaratilgan bo‘lishi mumkin.')
        output.write(block)
    return total


class FileEngine:
    def __init__(self, roots=None, storage=Path("data/computer")):
        self.storage = Path(storage).resolve()
        self.storage.mkdir(parents=True, exist_ok=True)
        self.root_settings = self.storage/'roots.json'
        self.custom_roots = []
        if roots is None:
            try:
                stored = json.loads(self.root_settings.read_text(encoding='utf-8'))
                if isinstance(stored, list):
                    for value in stored[:20]:
                        try:
                            self.custom_roots.append(self._checked_root(value))
                        except (ValueError, TypeError, OSError):
                            continue
            except (OSError, ValueError):
                pass
            roots = default_roots()+self.custom_roots
        self.scope = FileScope(roots, self.storage)
        self.index = FileIndex(self.scope, self.storage)
        self.lock = threading.RLock()
        self.journal = self.storage/"journal.json"
        self.plans = {}

    def _checked_root(self, value):
        if not isinstance(value, (str, Path)):
            raise ValueError('Papka yo‘li matn bo‘lsin.')
        path = Path(value)
        if not path.is_absolute() or not path.is_dir():
            raise ValueError('Mavjud lokal papkani tanlang.')
        probe = FileScope([path], self.storage)
        path = probe.path(path)
        if path == Path(path.anchor) or Path.home().resolve().is_relative_to(path):
            raise ValueError('Butun disk yoki butun foydalanuvchi hududi emas, alohida ish papkasini tanlang.')
        return path

    def add_root(self, value):
        """Called only by the explicit folder picker + human consent in Computer Hub.

        Deliberately absent from the AI capability catalog.
        """
        with self.lock:
            path = self._checked_root(value)
            if any(path.is_relative_to(root) for root in self.scope.roots):
                return path
            if len(self.custom_roots) >= 20:
                raise ValueError('Ko‘pi bilan 20 ta qo‘shimcha ish papkasi.')
            roots = self.custom_roots+[path]
            draft = self.root_settings.with_suffix('.tmp')
            draft.write_text(json.dumps([str(root) for root in roots], ensure_ascii=False), encoding='utf-8')
            draft.replace(self.root_settings)
            self.custom_roots = roots
            self.scope = FileScope(self.scope.roots+[path], self.storage)
            self.index.scope = self.scope
            self.index.last = 0
            return path

    def path(self, value, **kwargs):
        if not Path(value).is_absolute() and kwargs.get("exists", True):
            matches = [row for row in self.index.rows(value) if Path(row["path"]).name.casefold() == value.casefold()]
            if len(matches) != 1:
                raise ValueError("Aniq bitta fayl tanlang. Mos yo'llar: " + json.dumps(matches[:8], ensure_ascii=False))
            value = matches[0]["path"]
        return self.scope.path(value, **kwargs)

    def _entries(self, root, *, include_dirs=False):
        if not root.is_dir():
            raise ValueError('Papka tanlang.')
        paths, total, count = [], 0, 0
        deadline = time.monotonic()+15
        def fail(error):
            raise error
        for folder, dirs, files in os.walk(root, followlinks=False, onerror=fail):
            if time.monotonic() > deadline:
                raise ValueError('Papka tekshirish vaqti tugadi; kichikroq papka tanlang.')
            for name in dirs+files:
                path = Path(folder)/name
                count += 1
                if not self.scope.allowed(path) or linked(path) or name.startswith("."):
                    raise ValueError("Papkada maxfiy/hidden/symlink yo'l bor; butun papka amali rad etildi.")
                if path.is_file():
                    size = path.stat().st_size
                    total += size
                    if size > MAX_FILE:
                        raise ValueError('Papkada 100 MB dan katta fayl bor.')
                    paths.append(path)
                elif include_dirs:
                    paths.append(path)
                if count > MAX_ENTRIES or total > MAX_TOTAL:
                    raise ValueError('Papka 10000 yozuv yoki 300 MB chegarasidan katta.')
        return paths

    def _text(self, path):
        if path.suffix.casefold() not in TEXT_TYPES or path.stat().st_size > 2*1024*1024:
            raise ValueError("Matn amali uchun UTF-8 matn fayli (2 MB gacha) kerak; Office uchun Office Studio'dan foydalaning.")
        try:
            return path.read_text(encoding="utf-8-sig")
        except UnicodeError as error:
            raise ValueError("Fayl UTF-8 matn emas; kodlashni taxmin qilib o'zgartirmayman.") from error

    def _records(self):
        return json.loads(self.journal.read_text(encoding="utf-8")) if self.journal.exists() else []

    def _record(self, data):
        records = self._records()
        data = dict(data, id=uuid.uuid4().hex, time=time.time())
        records.append(data)
        temporary = self.journal.with_suffix(".tmp")
        temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.journal)
        return data["id"]

    def _write(self, path, text):
        if path.suffix.casefold() not in TEXT_TYPES or len(text.encode("utf-8")) > 2*1024*1024:
            raise ValueError("Faqat 2 MB gacha bo'lgan matnli fayl yoziladi.")
        if not path.parent.is_dir():
            raise ValueError("Saqlash papkasi mavjud emas.")
        if not path.exists():
            with path.open("x", encoding="utf-8") as stream:
                stream.write(text)
            return "Yangi matn fayli yaratildi: " + str(path)
        self._text(path)
        backups = self.storage/"backups"
        backups.mkdir(exist_ok=True)
        backup = backups/(uuid.uuid4().hex+path.suffix)
        expected = checksum(path)
        shutil.copy2(path, backup)
        if checksum(backup) != expected:
            raise ValueError('Zaxira vaqtida fayl o‘zgardi; tahrir bekor qilindi.')
        raw = path.read_bytes()
        encoding = 'utf-8-sig' if raw.startswith(b'\xef\xbb\xbf') else 'utf-8'
        if b'\r\n' in raw and b'\n' not in raw.replace(b'\r\n', b''):
            text = text.replace('\r\n', '\n').replace('\n', '\r\n')
        self._records()  # Refuse edits if the existing recovery journal is corrupt.
        handle, name = tempfile.mkstemp(prefix=".jarvis-", dir=path.parent)
        draft = Path(name)
        try:
            with os.fdopen(handle, "w", encoding=encoding, newline="") as stream:
                stream.write(text)
            if checksum(path) != expected:
                raise ValueError("Fayl tashqaridan o'zgardi; tahrir bekor qilindi.")
            draft.replace(path)
        finally:
            draft.unlink(missing_ok=True)
        identifier = self._record({"kind": "edit", "path": str(path), "backup": str(backup), "after": checksum(path)})
        return f"Matn yangilandi, zaxira olindi. Qaytarish ID: {identifier}\n{path}"

    def execute(self, key, args):
        with self.lock:
            return self._execute(key, args)

    def _execute(self, key, args):
        limit = max(1, min(100, int(args.get("limit") or 30)))
        if key in {"file_find", "largest_files", "recent_files", "inventory_export", "text_search", "duplicates"}:
            rows = self.index.rows(args.get("query", "") if key == "file_find" else "", args.get("root"),
                                   order={"largest_files": "size", "recent_files": "mtime"}.get(key, "name"), limit=10000 if key in {"inventory_export", "text_search", "duplicates"} else limit)
            if key == "text_search":
                result, read_bytes = [], 0
                deadline = time.monotonic()+10
                for row in rows:
                    if time.monotonic() > deadline or read_bytes > 30*1024*1024:
                        break
                    path = Path(row["path"])
                    if path.suffix.casefold() not in TEXT_TYPES or row["size"] > 1024*1024:
                        continue
                    try:
                        self.scope.path(path)
                        read_bytes += path.stat().st_size
                        for number, line in enumerate(self._text(path).splitlines(), 1):
                            if args["query"].casefold() in line.casefold():
                                result.append({"path": str(path), "line": number, "preview": line[:250]})
                                if len(result) >= limit:
                                    return {"matches": result, "bounded": True}
                    except (OSError, ValueError):
                        pass
                return {"matches": result, "bounded": True}
            if key == "duplicates":
                sizes = {}
                for row in rows:
                    sizes.setdefault(row["size"], []).append(row["path"])
                hashes = {}
                total = 0
                deadline = time.monotonic()+15
                for size, paths in sizes.items():
                    if len(paths) < 2 or size > MAX_FILE:
                        continue
                    for path in paths:
                        path = self.scope.path(path)
                        total += path.stat().st_size
                        if time.monotonic() > deadline:
                            raise ValueError('Dublikat tekshirish vaqti tugadi; kichikroq papka tanlang.')
                        if total > MAX_TOTAL:
                            raise ValueError("Dublikat hash o'qish chegarasi 300 MB; kichikroq root tanlang.")
                        hashes.setdefault(checksum(path), []).append(str(path))
                return {"groups": [paths for paths in hashes.values() if len(paths) > 1], "bounded": True}
            if key == "inventory_export":
                output = self.storage/("inventory-"+uuid.uuid4().hex[:8]+".csv")
                with output.open("x", newline="", encoding="utf-8-sig") as stream:
                    writer = csv.writer(stream)
                    writer.writerow(["path", "bytes", "modified"])
                    writer.writerows([row["path"], row["size"], row["modified"]] for row in rows)
                return {"file": str(output), "rows": len(rows), "bounded": True}
            return {"matches": rows, "bounded": True, "note": "Chegaralangan lokal indeks; butun disk bo'yicha yo'q degan xulosa emas."}
        if key == "backup_list":
            return self._records()[-100:]
        if key == "backup_restore":
            record = next((record for record in self._records() if record["id"] == args["id"]), None)
            if not record:
                raise ValueError("Zaxira ID topilmadi.")
            path = self.path(record["path"], mutate=True)
            if record["kind"] == "edit":
                if checksum(path) != record["after"]:
                    raise ValueError("Fayl keyin o'zgargan; yangi ishni yo'qotmaslik uchun qaytarish rad etildi.")
                backup = Path(record['backup']).resolve()
                if not backup.is_relative_to(self.storage/'backups') or linked(backup):
                    raise ValueError('Zaxira yo‘li noto‘g‘ri.')
                return self._write(path, self._text(backup))
            if record["kind"] == "move":
                original = self.scope.path(record["original"], exists=False, mutate=True)
                if original.exists() or not path.is_file() or checksum(path) != record["after"]:
                    raise ValueError("Ko'chirilgan fayl holati o'zgargan yoki eski manzil band.")
                path.rename(original)
                self.index.last = 0
                return "Fayl eski joyiga qaytarildi: " + str(original)
            raise ValueError("Bu tarix turi avtomatik qaytarilmaydi; zaxira faylini tanlang.")
        if key == "organize_apply":
            plan = self.plans.get(args["id"])
            if plan is None:
                raise ValueError("Reja topilmadi; avval organize_preview bajaring.")
            for source, destination, digest in plan:
                source = self.path(source, mutate=True)
                destination = self.scope.path(destination, exists=False, mutate=True)
                if not source.is_file() or checksum(source) != digest or destination.exists():
                    raise ValueError("Rejadan keyin fayllar o'zgargan; reja yangilansin.")
            results = []
            for source, destination, digest in plan:
                Path(destination).parent.mkdir(exist_ok=True)
                results.append(self._execute("file_move", {"path": source, "destination": destination}))
            self.plans.pop(args["id"], None)
            return results
        path = self.path(args["path"], exists=key not in {"text_create", "folder_create"}, mutate=key in {
            "text_create", "text_append", "text_replace", "file_rename", "folder_rename", "file_move", "folder_move", "file_recycle", "folder_create"})
        if key == "file_info":
            info = path.stat()
            return {"path": str(path), "bytes": info.st_size, "modified": info.st_mtime, "kind": "folder" if path.is_dir() else path.suffix}
        if key == "folder_list":
            return list(islice((str(child) for child in path.iterdir() if self.scope.allowed(child) and not linked(child)), 200))
        if key == "text_read":
            text = self._text(path)
            return {"path": str(path), "text": text[:24000], "truncated": len(text) > 24000}
        if key in {"text_create", "text_append", "text_replace"}:
            text = args.get("text", "")
            if key == "text_create" and path.exists():
                raise ValueError("Mavjud fayl ustiga yozilmaydi; yangi nom tanlang.")
            if key == "text_append":
                text = self._text(path)+text
            if key == "text_replace":
                original = self._text(path)
                if not args["old"] or args["old"] not in original:
                    raise ValueError("Almashtiriladigan aniq eski matn topilmadi.")
                text = original.replace(args["old"], args["new"])
            result = self._write(path, text)
            self.index.last = 0
            return result
        if key == "folder_create":
            path.mkdir()
            return "Papka yaratildi: " + str(path)
        if key in {"file_rename", "folder_rename", "file_move", "folder_move", "file_copy", "folder_copy"}:
            directory = key.startswith("folder")
            if path.is_dir() != directory:
                raise ValueError("Fayl/papka turi mos emas.")
            if key.endswith("rename"):
                name = args["name"]
                valid_name(name)
                destination = path.with_name(name)
            else:
                destination = self.scope.path(args["destination"], exists=False, mutate=True)
                if destination.is_dir():
                    destination = destination/path.name
            destination = self.scope.path(destination, exists=False, mutate=True)
            if destination.exists() or not destination.parent.is_dir() or destination.is_relative_to(path):
                raise ValueError("Natija manzili band, ota papkasi yo'q yoki o'z ichiga ko'chirilmoqda.")
            if directory:
                entries = self._entries(path)
            elif path.stat().st_size > MAX_FILE:
                raise ValueError("Fayl amali 100 MB bilan cheklangan.")
            if key.endswith("copy"):
                if directory:
                    # Copy only the validated manifest, never new unchecked files that
                    # appear during the operation. Empty directories are preserved.
                    directories = []
                    for folder, dirs, files in os.walk(path, followlinks=False):
                        directories.append(self.scope.path(folder).relative_to(path))
                        if len(directories) > MAX_ENTRIES:
                            raise ValueError('Papka tarkibi o‘zgardi; amal bekor qilindi.')
                    destination.mkdir()
                    for relative in directories:
                        self.scope.path(destination/relative, exists=False, mutate=True).mkdir(parents=True, exist_ok=True)
                    copied = 0
                    for source in entries:
                        source = self.scope.path(source)
                        target = self.scope.path(destination/source.relative_to(path), exists=False, mutate=True)
                        with source.open('rb') as input_file, target.open('xb') as output_file:
                            copied += bounded_copy(input_file, output_file, min(MAX_FILE, MAX_TOTAL-copied))
                else:
                    with path.open("rb") as source, destination.open("xb") as output:
                        bounded_copy(source, output)
            else:
                if path.stat().st_dev != destination.parent.stat().st_dev:
                    raise ValueError("Disklar orasida avval nusxa oling; atomik move faqat bitta diskda.")
                digest = checksum(path) if not directory else None
                path.rename(destination)
                if not directory:
                    self._record({"kind": "move", "original": str(path), "path": str(destination), "after": digest})
            self.index.last = 0
            return "Natija: " + str(destination)
        if key == "file_recycle":
            if not path.is_file():
                raise ValueError("Faqat alohida fayl Recycle Bin'ga yuboriladi, butun papka emas.")
            from send2trash import send2trash
            send2trash(str(path))
            self.index.last = 0
            return "Fayl Recycle Bin'ga yuborildi; Windows Recycle Bin orqali qaytarish mumkin."
        if key in {"file_checksum", "file_compare", "text_diff"}:
            if key == "file_checksum":
                return {"path": str(path), "sha256": checksum(path)}
            other = self.path(args["other"])
            if key == "file_compare":
                return {"same": checksum(path) == checksum(other)}
            first, second = self._text(path), self._text(other)
            if len(first)+len(second) > 200000:
                raise ValueError('Matn farqini ko‘rish uchun jami 200000 belgigacha; katta faylga hash taqqoslashni ishlating.')
            return "\n".join(islice(difflib.unified_diff(first.splitlines(), second.splitlines(), fromfile=str(path), tofile=str(other)), 500))
        if key in {"folder_stats", "folder_tree"}:
            if not path.is_dir():
                raise ValueError('Papka tanlang.')
            rows = list(self.scope.walk(str(path)))
            return {"files": len(rows), "bytes": sum(row.stat().st_size for row in rows), "bounded": True,
                    "tree": [str(row.relative_to(path)) for row in rows[:200]] if key == "folder_tree" else []}
        if key == "organize_preview":
            plan, total = [], 0
            for source in sorted(path.iterdir()):
                if source.is_file() and self.scope.allowed(source) and not linked(source) and source.stat().st_size <= MAX_FILE:
                    total += source.stat().st_size
                    if total > MAX_TOTAL:
                        raise ValueError('Saralash hash chegarasi 300 MB.')
                    destination = path/(source.suffix.lstrip(".").upper() or "OTHER")/source.name
                    if destination.exists():
                        raise ValueError("Saralashda nom to'qnashuvi bor: " + str(destination))
                    plan.append((str(source), str(destination), checksum(source)))
                    if len(plan) > 300:
                        raise ValueError("Bir saralash rejasi 300 faylgacha.")
            identifier = uuid.uuid4().hex
            if len(self.plans) >= 20:
                self.plans.pop(next(iter(self.plans)))
            self.plans[identifier] = plan
            return {"plan_id": identifier, "moves": [(source, target) for source, target, _ in plan]}
        if key in {"zip_create", "folder_snapshot"}:
            sources = self._entries(path, include_dirs=True) if path.is_dir() else [path]
            if any(source.stat().st_size > MAX_FILE for source in sources):
                raise ValueError("Arxiv ichidagi fayl 100 MB dan katta.")
            output = self.storage/("snapshot-"+uuid.uuid4().hex+".zip") if key == "folder_snapshot" else self.scope.path(args["destination"], exists=False, mutate=True)
            if output.suffix.casefold() != ".zip" or output.exists() or (path.is_dir() and output.is_relative_to(path)):
                raise ValueError("Yangi ZIP manzili manba papka tashqarisida bo'lsin.")
            with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED) as archive:
                for source in sources:
                    source = self.scope.path(source)
                    name = str(source.relative_to(path) if path.is_dir() else source.name)
                    if source.is_dir():
                        archive.write(source, name)
                    else:
                        info = zipfile.ZipInfo.from_file(source, name)
                        info.compress_type = zipfile.ZIP_DEFLATED
                        with source.open('rb') as input_file, archive.open(info, 'w') as output_file:
                            bounded_copy(input_file, output_file)
            if key == "folder_snapshot":
                self._record({"kind": "snapshot", "path": str(path), "backup": str(output)})
            return "ZIP yaratildi: " + str(output)
        if key in {"zip_inspect", "zip_extract"}:
            if path.stat().st_size > MAX_FILE:
                raise ValueError('ZIP kirish fayli 100 MB dan katta.')
            with zipfile.ZipFile(path) as archive:
                entries = archive.infolist()
                if len(entries) > MAX_ENTRIES or sum(entry.file_size for entry in entries) > MAX_TOTAL or any(entry.file_size > MAX_FILE for entry in entries):
                    raise ValueError("Arxiv ochilganda xavfsiz hajm chegarasidan oshadi.")
                names = []
                seen = set()
                for entry in entries:
                    name = PurePosixPath(entry.filename.replace("\\", "/"))
                    if name.is_absolute() or ".." in name.parts or any(":" in part for part in name.parts) or stat.S_ISLNK(entry.external_attr >> 16) or entry.flag_bits & 1:
                        raise ValueError("Arxivda traversal, symlink yoki shifrlangan nishon bor.")
                    if not name.parts or str(name).casefold() in seen:
                        raise ValueError('Arxivda bo‘sh yoki takrorlangan nom bor.')
                    for part in name.parts:
                        valid_name(part)
                    seen.add(str(name).casefold())
                    names.append(str(name))
                files = {name.casefold() for entry, name in zip(entries, names) if not entry.is_dir()}
                if any(str(parent).casefold() in files for name in names for parent in PurePosixPath(name).parents if str(parent) != '.'):
                    raise ValueError('Arxivda fayl va ota papka nomlari to‘qnashgan.')
                if key == "zip_inspect":
                    return {"count": len(names), "bytes": sum(entry.file_size for entry in entries), "names": names[:200]}
                destination = self.scope.path(args["destination"], exists=False, mutate=True)
                if destination.exists():
                    raise ValueError("Arxiv faqat yangi papkaga ochiladi.")
                for name in names:
                    self.scope.path(destination/name, exists=False, mutate=True)
                destination.mkdir()
                for entry, name in zip(entries, names):
                    target = destination/name
                    if entry.is_dir():
                        target.mkdir(parents=True, exist_ok=True)
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(entry) as source, target.open("xb") as output:
                            bounded_copy(source, output)
                self.index.last = 0
                return "Arxiv ochildi: " + str(destination)
        if key in {"file_open", "file_reveal", "clipboard_copy_path"}:
            from .platform import open_file, reveal_file
            if key == "clipboard_copy_path":
                import pyperclip
                pyperclip.copy(str(path))
                return "Yo'l clipboardga olindi."
            return open_file(path) if key == "file_open" else reveal_file(path)
        raise ValueError("Fayl qobiliyati amalga oshirilmagan: " + key)
