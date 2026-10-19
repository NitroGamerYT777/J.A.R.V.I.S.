"""One-shot COM PDF worker. Never attaches to a user's existing Office process."""

from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sys
import time
from typing import Callable


def _com_retry(operation: Callable, *args, **kwargs):
    """Office briefly rejects calls while calculating/paginating. Never retry other errors."""
    for attempt in range(12):
        try:
            return operation(*args, **kwargs)
        except Exception as exc:
            hresult = getattr(exc, "hresult", exc.args[0] if exc.args else None)
            if hresult not in {-2147418111, -2147417846} or attempt == 11:
                raise
            import pythoncom

            pythoncom.PumpWaitingMessages()
            time.sleep(0.2)


def _discard_private(operation: Callable, *args, **kwargs) -> None:
    try:
        _com_retry(operation, *args, **kwargs)
    except Exception:
        # Only used INSIDE _owned_process. Its kill-on-close job is the final
        # teardown if Office rejects Close/Quit while paginating/shutting down.
        # Do not hide an earlier export error or reject a verified PDF merely
        # because a private process's shutdown COM proxy is already unavailable.
        pass


def _named_processes(executable: str) -> set[int]:
    import win32api
    import win32process

    result = set()
    for pid in win32process.EnumProcesses():
        handle = None
        try:
            handle = win32api.OpenProcess(0x0400 | 0x0010, False, pid)  # QUERY_INFORMATION | VM_READ
            if Path(win32process.GetModuleFileNameEx(handle, 0)).name.casefold() == executable.casefold():
                result.add(pid)
        except Exception:
            pass  # Access to unrelated system processes is unnecessary.
        finally:
            if handle is not None:
                handle.Close()
    return result


def _application_pid(application: object, previous_processes: set[int], extension: str) -> int:
    import win32process

    if extension == ".pptx":
        # PowerPoint exposes no reliable public Application HWND. It may also
        # reuse a process despite DispatchEx. Refuse any existing PowerPoint
        # before dispatch (office_pdf) and demand exactly one NEW process here.
        processes = _named_processes("POWERPNT.EXE")
        if processes & previous_processes or len(processes - previous_processes) != 1:
            raise ValueError("PowerPoint uchun alohida yangi jarayon aniqlanmadi; ochiq PowerPoint oynalarini yoping.")
        return (processes - previous_processes).pop()
    if extension == ".docx":
        # Word.Application has no HWND property. A private, empty document does;
        # no user file is opened until security and process ownership are ready.
        original_security = application.AutomationSecurity
        application.AutomationSecurity = 3
        blank = None
        try:
            blank = application.Documents.Add(Visible=False)
            window = int(blank.Windows.Item(1).Hwnd)
            _, pid = win32process.GetWindowThreadProcessId(window)
            if pid in previous_processes:
                application.AutomationSecurity = original_security
            return pid
        finally:
            if blank is not None:
                blank.Close(SaveChanges=False)
    window = int(application.Hwnd)
    _, pid = win32process.GetWindowThreadProcessId(window)
    return pid


@contextmanager
def _owned_process(application: object, previous_processes: set[int], extension: str):
    import win32api
    import win32job
    try:
        pid = _application_pid(application, previous_processes, extension)
    except Exception as exc:
        # Ownership was not established: never Quit an unknown/shared instance.
        raise ValueError("Office jarayoni egaligini tekshirib bo‘lmadi; ochiq Office oynalarini yoping va qayta urinib ko‘ring.") from exc
    if not pid or pid in previous_processes:
        raise ValueError("Office mavjud jarayonni qayta ishlatdi. Hujjatlaringiz xavfsizligi uchun Office oynalarini yoping va qayta urinib ko‘ring.")
    job = process = None
    try:
        job = win32job.CreateJobObject(None, "")
        information = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
        information["BasicLimitInformation"]["LimitFlags"] |= win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, information)
        process = win32api.OpenProcess(0x0100 | 0x0001, False, pid)  # SET_QUOTA | TERMINATE
        win32job.AssignProcessToJobObject(job, process)
    except Exception as exc:
        try:
            application.Quit()
        except Exception:
            pass
        if process is not None:
            process.Close()
        if job is not None:
            job.Close()
        raise ValueError("Office uchun xavfsiz ajratilgan konvertatsiya jarayonini yaratib bo‘lmadi.") from exc
    try:
        yield
    finally:
        # Also runs when the COM export fails. If this worker is killed on timeout,
        # Windows closes the job handle and terminates ONLY this verified new PID.
        process.Close()
        job.Close()


def _run_com(
    source: Path, destination: Path, dispatch: Callable, owner: Callable,
) -> str:
    extension = source.suffix.lower()
    program, backend = {
        ".docx": ("Word.Application", "Microsoft Word → PDF"),
        ".xlsx": ("Excel.Application", "Microsoft Excel → PDF"),
        ".pptx": ("PowerPoint.Application", "Microsoft PowerPoint → PDF"),
    }[extension]
    application = dispatch(program)
    document = None
    empty_workbook = None
    with owner(application):
        try:
            # Must precede Open: programmatic Office opening otherwise enables macros.
            application.AutomationSecurity = 3  # msoAutomationSecurityForceDisable
            if extension == ".docx":
                application.Visible = False
                application.DisplayAlerts = 0
                application.Options.UpdateLinksAtOpen = False
                application.Options.UpdateFieldsAtPrint = False
                application.Options.UpdateLinksAtPrint = False
                document = application.Documents.Open(
                    FileName=str(source), ConfirmConversions=False, ReadOnly=True,
                    AddToRecentFiles=False, Visible=False, OpenAndRepair=False,
                    PasswordDocument="", WritePasswordDocument="", NoEncodingDialog=True,
                )
                document.ExportAsFixedFormat(OutputFileName=str(destination), ExportFormat=17, OpenAfterExport=False)
            elif extension == ".xlsx":
                application.Visible = False
                application.DisplayAlerts = False
                application.EnableEvents = False
                application.AskToUpdateLinks = False
                # Excel cannot change Calculation when it has no workbook.
                # This blank private workbook has no user/source content.
                empty_workbook = application.Workbooks.Add()
                application.Calculation = -4135  # xlCalculationManual: no recalculation or external fetches
                document = application.Workbooks.Open(
                    Filename=str(source), UpdateLinks=0, ReadOnly=True, Password="", WriteResPassword="",
                    IgnoreReadOnlyRecommended=True, Notify=False, AddToMru=False,
                )
                # XML preflight has allowlisted ALL formulas, not just cells.
                # Recalculate missing/stale caches in this private instance;
                # never save these changes back to the original workbook.
                _com_retry(application.CalculateFullRebuild)
                _com_retry(document.ExportAsFixedFormat, Type=0, Filename=str(destination), OpenAfterPublish=False)
            else:
                application.DisplayAlerts = 1  # ppAlertsNone
                document = application.Presentations.Open(str(source), ReadOnly=True, Untitled=False, WithWindow=False)
                # PrintRange is REQUIRED by PowerPoint despite most examples
                # omitting it. None maps to COM Nothing (all slides).
                document.ExportAsFixedFormat(str(destination), 2, PrintRange=None)
        finally:
            if document is not None:
                if extension == ".pptx":
                    _discard_private(setattr, document, "Saved", True)  # NEVER Save original
                    _discard_private(document.Close)
                else:
                    _discard_private(document.Close, SaveChanges=False)
            if empty_workbook is not None:
                _discard_private(empty_workbook.Close, SaveChanges=False)
            _discard_private(application.Quit)
    if not destination.is_file() or destination.stat().st_size == 0:
        raise ValueError("Office natija faylini yaratmadi.")
    return backend


def office_pdf(source: Path, destination: Path) -> str:
    from .converters import _check_office_active_content, _check_source

    if destination.exists() or source.resolve() == destination.resolve():
        raise ValueError("Mavjud fayl ustiga yozish rad etildi.")
    if source.suffix.lower() not in {".docx", ".xlsx", ".pptx"} or destination.suffix.lower() != ".pdf":
        raise ValueError("Office worker faqat DOCX/XLSX/PPTX → PDF uchun.")
    _check_source(source)
    _check_office_active_content(source)
    import pythoncom
    import win32com.client
    import win32process

    pythoncom.CoInitialize()
    try:
        previous = set(win32process.EnumProcesses())
        if source.suffix.lower() == ".pptx" and _named_processes("POWERPNT.EXE"):
            raise ValueError("PDF yaratishdan avval ochiq PowerPoint oynalarini yoping. JARVIS mavjud PowerPoint jarayoniga tegmaydi.")
        return _run_com(source, destination, win32com.client.DispatchEx, lambda app: _owned_process(app, previous, source.suffix.lower()))
    finally:
        pythoncom.CoUninitialize()


def main() -> int:
    try:
        if len(sys.argv) != 3:
            raise ValueError("Worker uchun manba va natija fayl yo‘llari kerak.")
        backend = office_pdf(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
        response = {"ok": True, "backend": backend}
        status = 0
    except Exception as exc:
        response = {"ok": False, "error": "Office PDF xatosi: " + str(exc)[:600]}
        status = 1
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(response, ensure_ascii=False))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
