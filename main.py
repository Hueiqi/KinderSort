import sys
import os

# ========== CRITICAL FIX FOR PyInstaller ==========
# Force face_recognition to use the installed models folder
if getattr(sys, 'frozen', False):
    # Running as a bundled executable
    base_path = os.path.dirname(sys.executable)
    models_path = os.path.join(base_path, 'face_recognition_models')
    if os.path.exists(models_path):
        # Override the package path BEFORE any imports
        import face_recognition_models
        face_recognition_models.__path__ = [models_path]
        print(f"[INFO] Models loaded from: {models_path}")
    else:
        print(f"[WARNING] Models folder not found at: {models_path}")
# ==================================================

"""
main.py — KinderSort GUI entry point.

Single-window tkinter application that drives the PhotoSorter pipeline with a
background thread so the UI remains responsive during processing.
"""

import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from sorter import PhotoSorter
from utils import setup_logger

# ========== IMPORT SPLASH SCREEN ==========
from splash_screen import SplashScreen


class KinderSortApp(tk.Tk):
    """Main application window for KinderSort — Student Photo Organiser."""

    MIN_WIDTH = 500
    MIN_HEIGHT = 400

    def __init__(self) -> None:
        super().__init__()

        self.title("KinderSort Lite — AI Student Photo Organiser")
        self.minsize(self.MIN_WIDTH, self.MIN_HEIGHT)

        # Pipeline state tracking
        self._sorter_thread: threading.Thread | None = None
        self._is_running = False

        # UI StringVariables
        self._ref_var = tk.StringVar()
        self._events_var = tk.StringVar()
        self._output_var = tk.StringVar()

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # UI Layout Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construct the Tkinter layout components."""
        main_frame = ttk.Frame(self, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header section
        header_label = ttk.Label(
            main_frame,
            text="KinderSort Lite",
            font=("Segoe UI", 16, "bold"),
        )
        header_label.pack(anchor=tk.W, pady=(0, 2))

        sub_label = ttk.Label(
            main_frame,
            text="AI-powered offline student photo sorter for educators.",
            font=("Segoe UI", 9, "italic"),
        )
        sub_label.pack(anchor=tk.W, pady=(0, 15))

        # Folder selection form
        form_frame = ttk.LabelFrame(main_frame, text=" Folder Selection ", padding="10")
        form_frame.pack(fill=tk.X, pady=(0, 10))

        form_frame.columnconfigure(1, weight=1)

        # Row 0: Reference Photos
        ttk.Label(form_frame, text="Reference Folder:").grid(
            row=0, column=0, sticky=tk.W, pady=4, padx=(0, 8)
        )
        ttk.Entry(form_frame, textvariable=self._ref_var).grid(
            row=0, column=1, sticky=tk.EW, pady=4
        )
        ttk.Button(
            form_frame, text="Browse...", command=self._browse_ref
        ).grid(row=0, column=2, pady=4, padx=(8, 0))

        # Row 1: Event Photos
        ttk.Label(form_frame, text="Events Folder:").grid(
            row=1, column=0, sticky=tk.W, pady=4, padx=(0, 8)
        )
        ttk.Entry(form_frame, textvariable=self._events_var).grid(
            row=1, column=1, sticky=tk.EW, pady=4
        )
        ttk.Button(
            form_frame, text="Browse...", command=self._browse_events
        ).grid(row=1, column=2, pady=4, padx=(8, 0))

        # Row 2: Output Destination
        ttk.Label(form_frame, text="Output Folder:").grid(
            row=2, column=0, sticky=tk.W, pady=4, padx=(0, 8)
        )
        ttk.Entry(form_frame, textvariable=self._output_var).grid(
            row=2, column=1, sticky=tk.EW, pady=4
        )
        ttk.Button(
            form_frame, text="Browse...", command=self._browse_output
        ).grid(row=2, column=2, pady=4, padx=(8, 0))

        # Controls section
        ctrl_frame = ttk.Frame(main_frame)
        ctrl_frame.pack(fill=tk.X, pady=(0, 10))

        self._start_btn = ttk.Button(
            ctrl_frame, text="Start Sorting", command=self._start_sorting
        )
        self._start_btn.pack(side=tk.LEFT, padx=(0, 8))

        self._cancel_btn = ttk.Button(
            ctrl_frame,
            text="Cancel",
            command=self._cancel_sorting,
            state=tk.DISABLED,
        )
        self._cancel_btn.pack(side=tk.LEFT, padx=(0, 8))

        self._export_btn = ttk.Button(
            ctrl_frame, text="Export Report", command=self._on_export_report
        )
        self._export_btn.pack(side=tk.RIGHT)

        # Status & Progress Display
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=(0, 10))

        self._progress_bar = ttk.Progressbar(
            progress_frame, mode="determinate"
        )
        self._progress_bar.pack(fill=tk.X, pady=(0, 4))

        self._status_label = ttk.Label(
            progress_frame, text="Ready.", font=("Segoe UI", 9)
        )
        self._status_label.pack(anchor=tk.W)

        # Processing Summary Area
        summary_frame = ttk.LabelFrame(main_frame, text=" Summary ", padding="10")
        summary_frame.pack(fill=tk.BOTH, expand=True)

        self._summary_text = tk.Text(
            summary_frame,
            height=6,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("Consolas", 9),
        )
        self._summary_text.pack(fill=tk.BOTH, expand=True)

    # ------------------------------------------------------------------
    # Folder Dialog Handlers
    # ------------------------------------------------------------------

    def _browse_ref(self) -> None:
        path = filedialog.askdirectory(title="Select Student Reference Folder")
        if path:
            self._ref_var.set(path)

    def _browse_events(self) -> None:
        path = filedialog.askdirectory(title="Select Event Photos Folder")
        if path:
            self._events_var.set(path)

    def _browse_output(self) -> None:
        path = filedialog.askdirectory(title="Select Output Destination Folder")
        if path:
            self._output_var.set(path)

    # ------------------------------------------------------------------
    # Pipeline Thread Control
    # ------------------------------------------------------------------

    def _start_sorting(self) -> None:
        ref = self._ref_var.get().strip()
        events = self._events_var.get().strip()
        output = self._output_var.get().strip()

        if not ref or not events or not output:
            messagebox.showerror("Error", "Please select all three folders before starting.")
            return

        ref_path, events_path, output_path = Path(ref), Path(events), Path(output)

        if not ref_path.is_dir():
            messagebox.showerror("Error", f"Reference folder does not exist:\n{ref}")
            return
        if not events_path.is_dir():
            messagebox.showerror("Error", f"Events folder does not exist:\n{events}")
            return

        self._is_running = True
        self._start_btn.config(state=tk.DISABLED)
        self._cancel_btn.config(state=tk.NORMAL)
        self._progress_bar["value"] = 0
        self._clear_summary()
        self._set_status("Initializing AI engine...")

        self._sorter_thread = threading.Thread(
            target=self._run_pipeline,
            args=(ref_path, events_path, output_path),
            daemon=True,
        )
        self._sorter_thread.start()

    def _run_pipeline(self, ref_path: Path, events_path: Path, output_path: Path) -> None:
        start_time = time.time()
        logger = setup_logger(output_path / "kindersort.log")

        def progress_cb(current: int, total: int) -> None:
            if total > 0:
                pct = (current / total) * 100
                self.after(0, self._update_progress, pct, f"Processing photo {current} of {total}...")

        try:
            sorter = PhotoSorter(
                reference_folder=ref_path,
                events_folder=events_path,
                output_folder=output_path,
                logger=logger,
            )

            self.after(0, self._set_status, "Loading student reference embeddings...")
            num_students = sorter.load_references()

            if num_students == 0:
                self.after(
                    0,
                    self._on_pipeline_error,
                    "No valid student reference images found.",
                )
                return

            self.after(0, self._set_status, f"Loaded {num_students} student profiles. Sorting event photos...")
            counts = sorter.sort_events(progress_callback=progress_cb)

            elapsed = time.time() - start_time
            mins, secs = divmod(int(elapsed), 60)
            formatted_time = f"{mins:02d}:{secs:02d}"

            summary_msg = (
                f"Sorting completed in {formatted_time}.\n\n"
                f"  Total Photos Processed: {counts['total']}\n"
                f"  Photos Matched:          {counts['matched']}\n"
                f"  Unmatched Photos:        {counts['unmatched']}\n"
                f"  Skipped Files:          {counts['skipped']}\n"
            )

            self.after(0, self._on_pipeline_done, summary_msg, formatted_time)

        except Exception as e:
            self.after(0, self._on_pipeline_error, str(e))

    def _cancel_sorting(self) -> None:
        if self._is_running:
            self._is_running = False
            self._set_status("Cancelling operation...")
            self._cancel_btn.config(state=tk.DISABLED)

    def _update_progress(self, pct: float, status_text: str) -> None:
        self._progress_bar["value"] = pct
        self._status_label.config(text=status_text)

    def _on_pipeline_done(self, summary_text: str, formatted_time: str) -> None:
        self._is_running = False
        self._start_btn.config(state=tk.NORMAL)
        self._cancel_btn.config(state=tk.DISABLED)
        self._progress_bar["value"] = 100
        self._set_status("Complete.")
        self._write_summary(summary_text)

        messagebox.showinfo(
            "Sorting Complete",
            f"Done in {formatted_time}!\nCheck output folder for results.",
        )

    def _on_pipeline_error(self, error_msg: str) -> None:
        self._is_running = False
        self._start_btn.config(state=tk.NORMAL)
        self._cancel_btn.config(state=tk.DISABLED)
        self._set_status("An error occurred during processing.")
        messagebox.showerror("Execution Error", error_msg)

    # ------------------------------------------------------------------
    # EXPORT REPORT
    # ------------------------------------------------------------------

    def _on_export_report(self) -> None:
        """Export a Word report with all sorted student photos."""
        output = self._output_var.get().strip()
        if not output:
            messagebox.showerror("Error", "Please select an Output folder first.")
            return

        try:
            from generate_report import generate_student_report
            report_path = Path(output) / "Student_Report.docx"
            
            # Triggers export and custom success dialog
            generate_student_report(output, str(report_path), parent_window=self)
            
        except ImportError:
            messagebox.showerror("Error", "Report generator script (generate_report.py) not found.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {e}")

    # ------------------------------------------------------------------
    # Window Life Cycle Handlers
    # ------------------------------------------------------------------

    def _on_close(self) -> None:
        if self._is_running:
            if not messagebox.askyesno(
                "Exit Confirmation",
                "Sorting is still in progress. Are you sure you want to exit?",
            ):
                return
        self.destroy()

    def _set_status(self, text: str) -> None:
        self._status_label.config(text=text)

    def _write_summary(self, text: str) -> None:
        self._summary_text.config(state=tk.NORMAL)
        self._summary_text.delete("1.0", tk.END)
        self._summary_text.insert(tk.END, text)
        self._summary_text.config(state=tk.DISABLED)

    def _clear_summary(self) -> None:
        self._write_summary("")


# ---------------------------------------------------------------------------
# Application Main Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    """Launch the KinderSort GUI application."""
    splash = SplashScreen()
    splash.update_status("Initializing engine...")
    time.sleep(1)
    splash.update_status("Loading biometric face recognition models...")
    time.sleep(1)
    splash.close()

    app = KinderSortApp()
    app.mainloop()


if __name__ == "__main__":
    main()