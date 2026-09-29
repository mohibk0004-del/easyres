"""Run blocking system calls off the UI thread."""

import traceback

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

_live_tasks = set()


class _Signals(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)


class _Task(QRunnable):
    def __init__(self, fn, args, kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = _Signals()

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as exc:
            traceback.print_exc()
            self.signals.failed.emit(str(exc) or exc.__class__.__name__)
        else:
            self.signals.finished.emit(result)


def run_async(fn, *args, on_done=None, on_error=None, **kwargs):
    """Run fn(*args, **kwargs) on the thread pool.

    on_done(result) / on_error(message) are delivered on the UI thread.
    """
    task = _Task(fn, args, kwargs)
    _live_tasks.add(task.signals)

    def release(*_):
        _live_tasks.discard(task.signals)

    if on_done:
        task.signals.finished.connect(on_done)
    if on_error:
        task.signals.failed.connect(on_error)
    task.signals.finished.connect(release)
    task.signals.failed.connect(release)
    QThreadPool.globalInstance().start(task)
    return task
