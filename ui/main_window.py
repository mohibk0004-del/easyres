"""Compatibility alias. The window now lives in ui.app_window and its state
and actions in ui.controller."""

from ui.app_window import AppWindow as MainWindow

__all__ = ["MainWindow"]
