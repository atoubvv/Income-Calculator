import os
import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

import customtkinter as ctk
from tkinter import filedialog
from tkcalendar import Calendar

import load
import save
import calc
import pdfextracter  # <-- uses your existing pdfextracter.py

# ---------------------------------------------------------------------
# App icon management
# ---------------------------------------------------------------------

def resource_path(relative: str) -> Path:
    # works for normal run + PyInstaller
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative
    return Path(__file__).resolve().parent / relative

ICON_ICO = resource_path("assets/app.ico")

def set_app_icon(win: ctk.CTk):
    # Windows .ico
    try:
        win.iconbitmap(str(ICON_ICO))
    except Exception:
        pass

# ---------------------------------------------------------------------
# Always run relative to GUI.py so save.json reads/writes are consistent
# ---------------------------------------------------------------------
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent  # folder of the .exe
else:
    BASE_DIR = Path(__file__).resolve().parent

os.chdir(BASE_DIR)
SAVE_FILE = BASE_DIR / "save.json"

# ---------------------------------------------------------------------
# Default save.json (must exist BEFORE ensure_save_exists/read_raw_save)
# ---------------------------------------------------------------------
DEFAULT_SAVE = {
    "Balance": "0",
    "Expenses": [],
    "lastPayCheck": "0",
    "Debts": [],
    "Settings": {
        "appearance_mode": "Dark",
        "color_theme": "blue",
        "use_paychecks": False,
        "last_paycheck_file": ""
    },
    "path": ""
}

# -----------------------------
# Helpers: save.json management
# -----------------------------
def ensure_save_exists():
    if not SAVE_FILE.exists():
        with SAVE_FILE.open("w", encoding="utf-8") as f:
            json.dump(DEFAULT_SAVE, f, indent=4)


def read_raw_save() -> dict:
    # if file missing → create defaults first
    ensure_save_exists()

    try:
        with SAVE_FILE.open("r", encoding="utf-8") as f:
            text = f.read().strip()

        # empty file → treat as corrupted and reset
        if not text:
            raise ValueError("save.json is empty")

        return json.loads(text)

    except (json.JSONDecodeError, ValueError) as e:
        # backup the broken file so you don't lose it completely
        backup = SAVE_FILE.with_suffix(".broken.json")
        try:
            SAVE_FILE.replace(backup)
        except Exception:
            pass  # if replace fails, we'll just overwrite

        # write fresh defaults
        with SAVE_FILE.open("w", encoding="utf-8") as f:
            json.dump(DEFAULT_SAVE, f, indent=4)

        return DEFAULT_SAVE.copy()

def write_raw_save(data: dict):
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def ensure_settings_defaults(data: dict) -> dict:
    data.setdefault("Balance", "0")
    data.setdefault("Expenses", [])
    data.setdefault("lastPayCheck", "0")
    data.setdefault("Debts", [])
    data.setdefault("path", "")

    data.setdefault("Settings", {})
    data["Settings"].setdefault("appearance_mode", "Dark")
    data["Settings"].setdefault("color_theme", "blue")
    data["Settings"].setdefault("use_paychecks", False)
    data["Settings"].setdefault("last_paycheck_file", "")

    return data


def set_setting(key: str, value: Any):
    data = ensure_settings_defaults(read_raw_save())
    data["Settings"][key] = value
    write_raw_save(data)

def set_path(new_path: str):
    data = ensure_settings_defaults(read_raw_save())
    data["path"] = new_path
    write_raw_save(data)

def get_use_paychecks() -> bool:
    data = ensure_settings_defaults(read_raw_save())
    return bool(data["Settings"].get("use_paychecks", False))

def get_path() -> str:
    data = ensure_settings_defaults(read_raw_save())
    return str(data.get("path", "")).strip()

def get_balance_str() -> str:
    data = ensure_settings_defaults(read_raw_save())
    return str(data.get("Balance", "0"))

def set_balance_str(balance_str: str):
    """
    Uses your save.py to preserve your other data and keep Settings/path.
    """
    data = load.lastSave()
    save.save_data(balance_str, balance_str, data.get("Expenses", []), data.get("Debts", []))

def refresh_balance_from_pdf() -> tuple[bool, str]:
    """
    Uses your pdfextracter.py functions (no rewriting parser logic here).
    Returns (ok, message). If ok, also updates Balance + lastPayCheck.
    """
    try:
        folder = Path(get_path()).expanduser()
        if not folder.exists():
            return False, "Paycheck folder does not exist."

        latest_pdf = pdfextracter.pick_latest_pdf(folder)
        if not latest_pdf:
            return False, "No matching payslip PDFs found."

        text = pdfextracter.extract_pdf_text(latest_pdf)
        payout = pdfextracter.find_payout_amount(text)
        if not payout:
            return False, "Could not find payout amount in latest PDF."

        payout.file = latest_pdf.name

        # Store balance like your parser returns it ("1.024,09") so calc.py can parse it fine
        set_balance_str(payout.raw_amount)

        # Store metadata
        set_setting("last_paycheck_file", payout.file)

        return True, f"Loaded {payout.raw_amount}€ from {payout.file}"
    except Exception as e:
        return False, str(e)


# -----------------------------
# Helpers: formatting + validation
# -----------------------------
def sanitize_float_str(s: str) -> Optional[str]:
    """
    For expense inputs: store in a float() friendly format (dot decimal).
    Accepts "12,34" or "12.34" or "1.234,56".
    """
    if not s:
        return None
    s = s.strip().replace("€", "").replace(" ", "")
    # "1.234,56" -> "1234.56"
    s = s.replace(".", "").replace(",", ".")
    try:
        v = float(s)
        return f"{v:.2f}"
    except ValueError:
        return None

def sanitize_int_str(s: str) -> Optional[str]:
    if not s:
        return None
    s = s.strip().replace("€", "").replace(" ", "")
    try:
        v = int(float(s))  # allow "1000.0"
        return str(v)
    except ValueError:
        return None

def center_window(win: ctk.CTkToplevel, master: ctk.CTk, w: int, h: int):
    win.update_idletasks()
    mx = master.winfo_rootx()
    my = master.winfo_rooty()
    mw = master.winfo_width()
    mh = master.winfo_height()
    x = mx + (mw - w) // 2
    y = my + (mh - h) // 2
    win.geometry(f"{w}x{h}+{x}+{y}")


# -----------------------------
# UI: Modern modal dialogs
# -----------------------------
class ModalBase(ctk.CTkToplevel):
    def __init__(self, master, title: str, subtitle: str = "", w: int = 520, h: int = 360):
        super().__init__(master)
        set_app_icon(self)
        self.master = master
        self.title(title)
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        center_window(self, master, w, h)

        self.result = None

        self.container = ctk.CTkFrame(self, corner_radius=18)
        self.container.pack(fill="both", expand=True, padx=14, pady=14)

        head = ctk.CTkFrame(self.container, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(14, 6))

        ctk.CTkLabel(head, text=title, font=("ArialBold", 20)).pack(anchor="w")
        if subtitle:
            ctk.CTkLabel(head, text=subtitle, text_color="gray").pack(anchor="w", pady=(4, 0))

        self.body = ctk.CTkFrame(self.container, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=16, pady=10)

        self.footer = ctk.CTkFrame(self.container, fg_color="transparent")
        self.footer.pack(fill="x", padx=16, pady=(0, 14))

        self.status = ctk.CTkLabel(self.footer, text="", text_color="#DC3545")
        self.status.pack(side="left")

    def set_error(self, msg: str):
        self.status.configure(text=msg)

    def close(self):
        self.destroy()


class FormModal(ModalBase):
    """
    fields = [
      {"key":"name","label":"Name","placeholder":"Netflix","kind":"text"},
      {"key":"amount","label":"Amount (€)","placeholder":"12,99","kind":"float"},
    ]
    """
    def __init__(self, master, title: str, subtitle: str, fields: List[Dict[str, str]], w=560, h=420):
        super().__init__(master, title, subtitle, w=w, h=h)
        self.fields = fields
        self.inputs: Dict[str, ctk.CTkEntry] = {}

        grid = ctk.CTkFrame(self.body, fg_color="transparent")
        grid.pack(fill="both", expand=True)

        for i, f in enumerate(fields):
            ctk.CTkLabel(grid, text=f["label"], font=("ArialBold", 14)).grid(row=i*2, column=0, sticky="w", pady=(0, 4))
            ent = ctk.CTkEntry(grid, height=40, placeholder_text=f.get("placeholder", ""))
            ent.grid(row=i*2 + 1, column=0, sticky="we", pady=(0, 14))
            self.inputs[f["key"]] = ent

        grid.grid_columnconfigure(0, weight=1)

        btn_cancel = ctk.CTkButton(self.footer, text="Cancel", fg_color="transparent", border_width=1,
                                   command=self.close, height=40)
        btn_cancel.pack(side="right", padx=(10, 0))

        btn_ok = ctk.CTkButton(self.footer, text="Save", command=self._ok, height=40)
        btn_ok.pack(side="right")

        # focus first
        if fields:
            self.inputs[fields[0]["key"]].focus_set()

    def _ok(self):
        out: Dict[str, str] = {}
        for f in self.fields:
            key = f["key"]
            kind = f.get("kind", "text")
            val = self.inputs[key].get().strip()

            if kind == "text":
                if not val:
                    self.set_error("Please fill all fields.")
                    return
                out[key] = val

            elif kind == "float":
                v = sanitize_float_str(val)
                if v is None:
                    self.set_error("Amount must be a valid number (e.g. 12,99).")
                    return
                out[key] = v

            elif kind == "int":
                v = sanitize_int_str(val)
                if v is None:
                    self.set_error("Amount must be a whole number.")
                    return
                out[key] = v

            else:
                out[key] = val

        self.result = out
        self.close()

    @staticmethod
    def ask(master, title: str, subtitle: str, fields: List[Dict[str, str]], w=560, h=420) -> Optional[Dict[str, str]]:
        dlg = FormModal(master, title, subtitle, fields, w=w, h=h)
        master.wait_window(dlg)
        return dlg.result


class SelectModal(ModalBase):
    def __init__(self, master, title: str, subtitle: str, options: List[str], w=520, h=300):
        super().__init__(master, title, subtitle, w=w, h=h)
        self.options = options

        ctk.CTkLabel(self.body, text="Select:", font=("ArialBold", 14)).pack(anchor="w", pady=(0, 6))

        self.var = ctk.StringVar(value=options[0] if options else "")
        self.menu = ctk.CTkOptionMenu(self.body, values=options, variable=self.var, height=40)
        self.menu.pack(fill="x")

        btn_cancel = ctk.CTkButton(self.footer, text="Cancel", fg_color="transparent", border_width=1,
                                   command=self.close, height=40)
        btn_cancel.pack(side="right", padx=(10, 0))

        btn_ok = ctk.CTkButton(self.footer, text="Confirm", command=self._ok, height=40)
        btn_ok.pack(side="right")

    def _ok(self):
        if not self.options:
            self.set_error("No options available.")
            return
        self.result = self.var.get()
        self.close()

    @staticmethod
    def ask(master, title: str, subtitle: str, options: List[str]) -> Optional[str]:
        dlg = SelectModal(master, title, subtitle, options)
        master.wait_window(dlg)
        return dlg.result


class ChoiceModal(ModalBase):
    def __init__(self, master, title: str, subtitle: str, left_text="Immediate", right_text="One more payment", w=560, h=260):
        super().__init__(master, title, subtitle, w=w, h=h)

        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(fill="x", pady=16)

        def choose(v: bool):
            self.result = v
            self.close()

        ctk.CTkButton(row, text=left_text, height=46, command=lambda: choose(True)).pack(side="left", expand=True, fill="x", padx=(0, 8))
        ctk.CTkButton(row, text=right_text, height=46, command=lambda: choose(False)).pack(side="left", expand=True, fill="x", padx=(8, 0))

    @staticmethod
    def ask(master, title: str, subtitle: str, left_text="Immediate", right_text="One more payment") -> Optional[bool]:
        dlg = ChoiceModal(master, title, subtitle, left_text, right_text)
        master.wait_window(dlg)
        return dlg.result


class DatePickerModal(ModalBase):
    def __init__(self, master, title="Pick a date"):
        super().__init__(master, title, subtitle="Choose a date from the calendar", w=420, h=520)
        set_app_icon(self)
        self._chosen = None

        self.cal = Calendar(self.body, selectmode="day")
        self.cal.pack(padx=10, pady=10)

        btn_cancel = ctk.CTkButton(self.footer, text="Cancel", fg_color="transparent", border_width=1,
                                   command=self.close, height=40)
        btn_cancel.pack(side="right", padx=(10, 0))

        btn_ok = ctk.CTkButton(self.footer, text="OK", command=self._ok, height=40)
        btn_ok.pack(side="right")

    def _ok(self):
        d = self.cal.selection_get()
        self.result = d.strftime("%d.%m.%Y")
        self.close()

    @staticmethod
    def ask(master, title="Pick a date") -> Optional[str]:
        dlg = DatePickerModal(master, title=title)
        master.wait_window(dlg)
        return dlg.result


# -----------------------------
# UI: Pages
# -----------------------------
class Page(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app

    def refresh(self):
        pass


class HomePage(Page):
    def __init__(self, master, app):
        super().__init__(master, app)

        wrap = ctk.CTkFrame(self, corner_radius=18)
        wrap.pack(fill="both", expand=True, padx=18, pady=18)

        top = ctk.CTkFrame(wrap, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=(18, 10))

        ctk.CTkLabel(top, text="Overview", font=("ArialBold", 24)).pack(side="left")

        self.mode_pill = ctk.CTkLabel(top, text="", text_color="gray")
        self.mode_pill.pack(side="right")

        card = ctk.CTkFrame(wrap, corner_radius=16)
        card.pack(fill="x", padx=18, pady=(0, 14))

        self.balance_label = ctk.CTkLabel(card, text="", font=("ArialBold", 34))
        self.balance_label.pack(anchor="w", padx=18, pady=(16, 0))

        self.meta = ctk.CTkLabel(card, text="", text_color="gray")
        self.meta.pack(anchor="w", padx=18, pady=(6, 16))

        actions = ctk.CTkFrame(wrap, fg_color="transparent")
        actions.pack(fill="x", padx=18, pady=(0, 10))

        self.refresh_btn = ctk.CTkButton(actions, text="Refresh from latest PDF", height=44, command=self._refresh_pdf)
        self.refresh_btn.pack(side="left")

        ctk.CTkButton(actions, text="Open Calculations", height=44, command=lambda: self.app.show("calc")).pack(side="left", padx=(10, 0))

        self.status = ctk.CTkLabel(wrap, text="", text_color="gray")
        self.status.pack(anchor="w", padx=18, pady=(6, 18))

    def _refresh_pdf(self):
        ok, msg = refresh_balance_from_pdf()
        self.status.configure(text=("✓ " if ok else "⚠️ ") + msg, text_color=("#28A745" if ok else "#DC3545"))
        self.app.reload_data()
        self.refresh()

    def refresh(self):
        data = ensure_settings_defaults(read_raw_save())
        use_pdf = bool(data["Settings"].get("use_paychecks", False))
        bal = str(data.get("Balance", "0"))

        self.balance_label.configure(text=f"{bal}€")
        if use_pdf:
            file_name = data["Settings"].get("last_paycheck_file", "") or "—"
            self.mode_pill.configure(text="PDF mode: ON")
            self.meta.configure(text=f"Latest file: {file_name}")
            self.refresh_btn.configure(state="normal")
        else:
            self.mode_pill.configure(text="PDF mode: OFF")
            self.meta.configure(text="Manual income")
            self.refresh_btn.configure(state="disabled")


class SetupPage(Page):
    def __init__(self, master, app):
        super().__init__(master, app)

        wrap = ctk.CTkFrame(self, corner_radius=18)
        wrap.pack(fill="both", expand=True, padx=18, pady=18)

        ctk.CTkLabel(wrap, text="First Time Setup", font=("ArialBold", 28)).pack(anchor="w", padx=18, pady=(18, 6))
        ctk.CTkLabel(wrap, text="Choose your payslip folder and how income should be set.",
                     text_color="gray").pack(anchor="w", padx=18, pady=(0, 14))

        card = ctk.CTkFrame(wrap, corner_radius=16)
        card.pack(fill="x", padx=18, pady=(0, 14))

        self.use_var = ctk.BooleanVar(value=get_use_paychecks())
        self.use_switch = ctk.CTkSwitch(card, text="Use paychecks (PDF) automatically",
                                        variable=self.use_var, command=self._sync)
        self.use_switch.pack(anchor="w", padx=18, pady=(16, 8))

        self.balance_entry = ctk.CTkEntry(card, height=42, placeholder_text="Manual income (e.g. 1250 or 1.250,00)")
        self.balance_entry.pack(fill="x", padx=18, pady=(0, 14))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(0, 18))

        self.path_entry = ctk.CTkEntry(row, height=42, placeholder_text="Payslip folder path…")
        self.path_entry.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(row, text="Browse", width=120, height=42, command=self._browse).pack(side="left", padx=(10, 0))

        bottom = ctk.CTkFrame(wrap, fg_color="transparent")
        bottom.pack(fill="x", padx=18, pady=(0, 18))

        self.status = ctk.CTkLabel(bottom, text="", text_color="#DC3545")
        self.status.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(bottom, text="Confirm", height=44, command=self._confirm).pack(side="right")

        # preload
        p = get_path()
        if p:
            self.path_entry.insert(0, p)
        self._sync()

    def _browse(self):
        p = filedialog.askdirectory(title="Select paychecks folder")
        if p:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, p)

    def _sync(self):
        if self.use_var.get():
            self.balance_entry.configure(state="disabled")
        else:
            self.balance_entry.configure(state="normal")

    def _confirm(self):
        folder = self.path_entry.get().strip()
        if not folder or not Path(folder).exists():
            self.status.configure(text="Please select a valid folder path.")
            return

        set_path(folder)
        set_setting("use_paychecks", bool(self.use_var.get()))

        if self.use_var.get():
            ok, msg = refresh_balance_from_pdf()
            if not ok:
                self.status.configure(text=f"PDF parse failed: {msg}")
                return
        else:
            bal = self.balance_entry.get().strip() or "0"
            set_balance_str(bal)

        self.app.reload_data()
        self.app.enable_nav()
        self.app.show("home")


class ExpensesPage(Page):
    def __init__(self, master, app):
        super().__init__(master, app)

        wrap = ctk.CTkFrame(self, corner_radius=18)
        wrap.pack(fill="both", expand=True, padx=18, pady=18)

        top = ctk.CTkFrame(wrap, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=(18, 10))
        ctk.CTkLabel(top, text="Expenses", font=("ArialBold", 24)).pack(side="left")

        btns = ctk.CTkFrame(wrap, fg_color="transparent")
        btns.pack(fill="x", padx=18, pady=(0, 12))

        ctk.CTkButton(btns, text="Add one-time", height=40, command=self.add_one_time).pack(side="left")
        ctk.CTkButton(btns, text="Add monthly", height=40, command=self.add_monthly).pack(side="left", padx=(10, 0))
        ctk.CTkButton(btns, text="Remove", height=40, command=self.remove).pack(side="left", padx=(10, 0))
        ctk.CTkButton(btns, text="Cancel monthly", height=40, command=self.cancel_monthly).pack(side="left", padx=(10, 0))

        self.scroll = ctk.CTkScrollableFrame(wrap, corner_radius=14)
        self.scroll.pack(fill="both", expand=True, padx=18, pady=(0, 18))

    def _clear_list(self):
        for child in self.scroll.winfo_children():
            child.destroy()

    def refresh(self):
        self._clear_list()
        expenses = calc.get_expenses()

        if not expenses:
            ctk.CTkLabel(self.scroll, text="No expenses yet.", text_color="gray").pack(pady=18)
            return

        monthly = [e for e in expenses if e.get("is_monthly")]
        one = [e for e in expenses if not e.get("is_monthly")]

        if monthly:
            ctk.CTkLabel(self.scroll, text="MONTHLY", text_color="gray").pack(anchor="w", padx=10, pady=(10, 6))
            for e in monthly:
                self._item(e, monthly=True)

        if one:
            ctk.CTkLabel(self.scroll, text="ONE-TIME", text_color="gray").pack(anchor="w", padx=10, pady=(18, 6))
            for e in one:
                self._item(e, monthly=False)

    def _item(self, e: dict, monthly: bool):
        card = ctk.CTkFrame(self.scroll, corner_radius=14)
        card.pack(fill="x", padx=8, pady=6)

        left = ctk.CTkFrame(card, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True, padx=12, pady=10)

        ctk.CTkLabel(left, text=e["name"], font=("ArialBold", 16)).pack(anchor="w")
        sub = (f"{e['amount']} €/month" if monthly else f"{e['amount']} €")
        ctk.CTkLabel(left, text=sub, text_color="gray").pack(anchor="w", pady=(2, 0))

        tag = "Monthly" if monthly else "One-time"
        ctk.CTkLabel(card, text=tag, text_color="gray").pack(side="right", padx=12)

    def add_one_time(self):
        res = FormModal.ask(
            self,
            "Add Expense",
            "One-time expense",
            [
                {"key": "name", "label": "Name", "placeholder": "New headphones", "kind": "text"},
                {"key": "amount", "label": "Amount (€)", "placeholder": "49,99", "kind": "float"},
            ],
            h=420
        )
        if not res:
            return

        calc.add_expense(res["name"], res["amount"])
        self.refresh()

    def add_monthly(self):
        res = FormModal.ask(
            self,
            "Add Monthly Expense",
            "Recurring every month until cancelled",
            [
                {"key": "name", "label": "Name", "placeholder": "Netflix", "kind": "text"},
                {"key": "amount", "label": "Amount per month (€)", "placeholder": "12,99", "kind": "float"},
            ],
            h=420
        )
        if not res:
            return

        start = DatePickerModal.ask(self, "Pick start date")
        if not start:
            return

        calc.add_expense(res["name"], res["amount"], is_monthly=True, start_date=start)
        self.refresh()

    def remove(self):
        expenses = calc.get_expenses()
        if not expenses:
            return
        names = [e["name"] for e in expenses]
        pick = SelectModal.ask(self, "Remove Expense", "Pick an expense to remove", names)
        if not pick:
            return
        calc.remove_expense(pick)
        self.refresh()

    def cancel_monthly(self):
        expenses = calc.get_expenses()
        monthly = [e for e in expenses if e.get("is_monthly")]
        if not monthly:
            return
        names = [e["name"] for e in monthly]
        pick = SelectModal.ask(self, "Cancel Monthly Expense", "Pick the monthly expense", names)
        if not pick:
            return

        cancel_date = DatePickerModal.ask(self, "Pick cancel date")
        if not cancel_date:
            return

        immediate = ChoiceModal.ask(
            self,
            "Cancel Mode",
            "Cancel immediately or after one more payment?",
            left_text="Immediate",
            right_text="One more payment"
        )
        if immediate is None:
            return

        calc.cancel_monthly_expense(pick, cancel_date, immediate)
        self.refresh()


class DebtsPage(Page):
    def __init__(self, master, app):
        super().__init__(master, app)

        wrap = ctk.CTkFrame(self, corner_radius=18)
        wrap.pack(fill="both", expand=True, padx=18, pady=18)

        top = ctk.CTkFrame(wrap, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=(18, 10))
        ctk.CTkLabel(top, text="Debts", font=("ArialBold", 24)).pack(side="left")

        btns = ctk.CTkFrame(wrap, fg_color="transparent")
        btns.pack(fill="x", padx=18, pady=(0, 12))

        ctk.CTkButton(btns, text="Add one-time", height=40, command=self.add_one_time).pack(side="left")
        ctk.CTkButton(btns, text="Add monthly", height=40, command=self.add_monthly).pack(side="left", padx=(10, 0))
        ctk.CTkButton(btns, text="Remove", height=40, command=self.remove).pack(side="left", padx=(10, 0))

        self.scroll = ctk.CTkScrollableFrame(wrap, corner_radius=14)
        self.scroll.pack(fill="both", expand=True, padx=18, pady=(0, 18))

    def _clear_list(self):
        for child in self.scroll.winfo_children():
            child.destroy()

    def refresh(self):
        self._clear_list()
        debts = calc.get_debts()

        if not debts:
            ctk.CTkLabel(self.scroll, text="No debts yet.", text_color="gray").pack(pady=18)
            return

        monthly = [d for d in debts if d.get("debt_monthly") == "Yes"]
        one = [d for d in debts if d.get("debt_monthly") == "No"]

        if monthly:
            ctk.CTkLabel(self.scroll, text="MONTHLY", text_color="gray").pack(anchor="w", padx=10, pady=(10, 6))
            for d in monthly:
                self._item(d, monthly=True)

        if one:
            ctk.CTkLabel(self.scroll, text="ONE-TIME", text_color="gray").pack(anchor="w", padx=10, pady=(18, 6))
            for d in one:
                self._item(d, monthly=False)

    def _item(self, d: dict, monthly: bool):
        card = ctk.CTkFrame(self.scroll, corner_radius=14)
        card.pack(fill="x", padx=8, pady=6)

        left = ctk.CTkFrame(card, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True, padx=12, pady=10)

        ctk.CTkLabel(left, text=d["name"], font=("ArialBold", 16)).pack(anchor="w")
        if monthly:
            ctk.CTkLabel(left, text=f"{d['amount']} € total • {d['length']} months", text_color="gray").pack(anchor="w", pady=(2, 0))
            ctk.CTkLabel(left, text=f"Start: {d['start_date']}", text_color="gray").pack(anchor="w", pady=(2, 0))
        else:
            ctk.CTkLabel(left, text=f"{d['amount']} € • Pay: {d['start_date']}", text_color="gray").pack(anchor="w", pady=(2, 0))

        tag = "Monthly" if monthly else "One-time"
        ctk.CTkLabel(card, text=tag, text_color="gray").pack(side="right", padx=12)

    def add_one_time(self):
        res = FormModal.ask(
            self,
            "Add Debt",
            "One-time payment debt",
            [
                {"key": "name", "label": "Name", "placeholder": "Dentist bill", "kind": "text"},
                {"key": "amount", "label": "Amount (€)", "placeholder": "250", "kind": "int"},
            ],
            h=420
        )
        if not res:
            return

        date = DatePickerModal.ask(self, "Pick pay date")
        if not date:
            return

        calc.add_debt(res["name"], res["amount"], date, False, 0)
        self.refresh()

    def add_monthly(self):
        res = FormModal.ask(
            self,
            "Add Monthly Debt",
            "Split into equal monthly payments",
            [
                {"key": "name", "label": "Name", "placeholder": "Phone contract", "kind": "text"},
                {"key": "amount", "label": "Total amount (€)", "placeholder": "600", "kind": "int"},
                {"key": "length", "label": "Length (months)", "placeholder": "12", "kind": "int"},
            ],
            h=480
        )
        if not res:
            return

        start = DatePickerModal.ask(self, "Pick start date")
        if not start:
            return

        calc.add_debt(res["name"], res["amount"], start, True, res["length"])
        self.refresh()

    def remove(self):
        debts = calc.get_debts()
        if not debts:
            return
        names = [d["name"] for d in debts]
        pick = SelectModal.ask(self, "Remove Debt", "Pick a debt to remove", names)
        if not pick:
            return
        calc.remove_debt(pick)
        self.refresh()


class CalcPage(Page):
    def __init__(self, master, app):
        super().__init__(master, app)

        wrap = ctk.CTkFrame(self, corner_radius=18)
        wrap.pack(fill="both", expand=True, padx=18, pady=18)

        ctk.CTkLabel(wrap, text="Calculations", font=("ArialBold", 24)).pack(anchor="w", padx=18, pady=(18, 10))

        self.grid = ctk.CTkFrame(wrap, fg_color="transparent")
        self.grid.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        self.cards: Dict[str, ctk.CTkLabel] = {}

        def stat_card(title: str):
            card = ctk.CTkFrame(self.grid, corner_radius=16)
            t = ctk.CTkLabel(card, text=title, text_color="gray")
            v = ctk.CTkLabel(card, text="—", font=("ArialBold", 26))
            t.pack(anchor="w", padx=14, pady=(12, 0))
            v.pack(anchor="w", padx=14, pady=(6, 12))
            return card, v

        c1, v1 = stat_card("Total Expenses")
        c2, v2 = stat_card("Total Debt")
        c3, v3 = stat_card("Remaining Income")

        self.cards["expenses"] = v1
        self.cards["debt"] = v2
        self.cards["remaining"] = v3

        c1.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=(0, 10))
        c2.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=(0, 10))
        c3.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(10, 0))

        self.grid.grid_columnconfigure(0, weight=1)
        self.grid.grid_columnconfigure(1, weight=1)
        self.grid.grid_rowconfigure(1, weight=1)

        self.detail = ctk.CTkTextbox(self.grid, corner_radius=14)
        self.detail.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(14, 0))
        self.grid.grid_rowconfigure(2, weight=2)

    def refresh(self):
        total_expenses, total_monthly_expenses, total_onetime_expenses, total_one_time_debt, total_monthly_debt, total_debt, remaining_income = calc.Calculations()

        self.cards["expenses"].configure(text=f"{total_expenses:.2f}€")
        self.cards["debt"].configure(text=f"{total_debt:.2f}€")
        self.cards["remaining"].configure(text=f"{remaining_income:.2f}€")

        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("end",
                           f"Expenses:\n"
                           f"  Monthly:  {total_monthly_expenses:.2f}€\n"
                           f"  One-time: {total_onetime_expenses:.2f}€\n\n"
                           f"Debt:\n"
                           f"  Monthly:  {total_monthly_debt:.2f}€\n"
                           f"  One-time: {total_one_time_debt:.2f}€\n")
        self.detail.configure(state="disabled")


class SettingsPage(Page):
    def __init__(self, master, app):
        super().__init__(master, app)

        wrap = ctk.CTkFrame(self, corner_radius=18)
        wrap.pack(fill="both", expand=True, padx=18, pady=18)

        ctk.CTkLabel(wrap, text="Settings", font=("ArialBold", 24)).pack(anchor="w", padx=18, pady=(18, 10))

        card = ctk.CTkFrame(wrap, corner_radius=16)
        card.pack(fill="x", padx=18, pady=(0, 14))

        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=18, pady=18)

        ctk.CTkLabel(grid, text="Appearance Mode", font=("ArialBold", 14)).grid(row=0, column=0, sticky="w")
        self.appearance = ctk.CTkOptionMenu(grid, values=["Dark", "Light", "System"], command=self._set_appearance)
        self.appearance.grid(row=1, column=0, sticky="we", pady=(6, 14), padx=(0, 12))

        ctk.CTkLabel(grid, text="Color Theme", font=("ArialBold", 14)).grid(row=0, column=1, sticky="w")
        self.theme = ctk.CTkOptionMenu(grid, values=["blue", "dark-blue", "green"], command=self._set_theme)
        self.theme.grid(row=1, column=1, sticky="we", pady=(6, 14))

        self.use_var = ctk.BooleanVar(value=get_use_paychecks())
        self.use_switch = ctk.CTkSwitch(grid, text="Use paychecks (PDF) automatically",
                                        variable=self.use_var, command=self._toggle_use)
        self.use_switch.grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 14))

        ctk.CTkLabel(grid, text="Income / Balance", font=("ArialBold", 14)).grid(row=3, column=0, sticky="w")
        self.balance_entry = ctk.CTkEntry(grid, height=42)
        self.balance_entry.grid(row=4, column=0, sticky="we", pady=(6, 14), padx=(0, 12))

        self.refresh_btn = ctk.CTkButton(grid, text="Refresh from PDF", height=42, command=self._refresh_pdf)
        self.refresh_btn.grid(row=4, column=1, sticky="we", pady=(6, 14))

        ctk.CTkLabel(grid, text="Payslip folder", font=("ArialBold", 14)).grid(row=5, column=0, sticky="w")
        self.path_entry = ctk.CTkEntry(grid, height=42)
        self.path_entry.grid(row=6, column=0, sticky="we", pady=(6, 14), padx=(0, 12))

        ctk.CTkButton(grid, text="Browse", height=42, command=self._browse).grid(row=6, column=1, sticky="we", pady=(6, 14))

        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)

        footer = ctk.CTkFrame(wrap, fg_color="transparent")
        footer.pack(fill="x", padx=18, pady=(0, 18))

        self.status = ctk.CTkLabel(footer, text="", text_color="gray")
        self.status.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(footer, text="Save", height=44, command=self._save).pack(side="right")

    def _set_appearance(self, choice: str):
        set_setting("appearance_mode", choice)
        ctk.set_appearance_mode(choice.lower())
        self.status.configure(text="Saved appearance mode.", text_color="#28A745")
        self.app.reload_data()

    def _set_theme(self, choice: str):
        set_setting("color_theme", choice)
        ctk.set_default_color_theme(choice.lower())
        self.status.configure(text="Saved theme (may need restart).", text_color="#28A745")
        self.app.reload_data()

    def _toggle_use(self):
        set_setting("use_paychecks", bool(self.use_var.get()))
        self.refresh()

    def _browse(self):
        p = filedialog.askdirectory(title="Select paychecks folder")
        if p:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, p)

    def _refresh_pdf(self):
        # save path first
        set_path(self.path_entry.get().strip())

        ok, msg = refresh_balance_from_pdf()
        self.status.configure(text=("✓ " if ok else "⚠️ ") + msg,
                              text_color=("#28A745" if ok else "#DC3545"))
        self.app.reload_data()
        self.refresh()

    def _save(self):
        set_path(self.path_entry.get().strip())
        set_setting("use_paychecks", bool(self.use_var.get()))

        if not self.use_var.get():
            set_balance_str(self.balance_entry.get().strip() or "0")

        self.status.configure(text="✓ Saved.", text_color="#28A745")
        self.app.reload_data()
        self.refresh()

    def refresh(self):
        data = ensure_settings_defaults(read_raw_save())
        s = data["Settings"]

        self.appearance.set(s.get("appearance_mode", "Dark"))
        self.theme.set(s.get("color_theme", "blue"))

        use_pdf = bool(s.get("use_paychecks", False))
        self.use_var.set(use_pdf)

        self.balance_entry.delete(0, "end")
        self.balance_entry.insert(0, str(data.get("Balance", "0")))

        self.path_entry.delete(0, "end")
        self.path_entry.insert(0, str(data.get("path", "")))

        if use_pdf:
            self.balance_entry.configure(state="disabled")
            self.refresh_btn.configure(state="normal")
        else:
            self.balance_entry.configure(state="normal")
            self.refresh_btn.configure(state="disabled")


# -----------------------------
# App shell (sidebar layout)
# -----------------------------
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        set_app_icon(self)
        self.title("Income Calculator")
        self.geometry("1100x720")
        self.minsize(1000, 650)

        self.data = ensure_settings_defaults(read_raw_save())

        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")

        self.content = ctk.CTkFrame(self, corner_radius=0)
        self.content.pack(side="left", fill="both", expand=True)

        # Sidebar header
        head = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        head.pack(fill="x", padx=18, pady=(18, 10))
        ctk.CTkLabel(head, text="Income\nCalculator", font=("ArialBold", 22)).pack(anchor="w")
        ctk.CTkLabel(head, text="The Best out there.", text_color="gray").pack(anchor="w", pady=(2, 0))

        self.nav = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.nav.pack(fill="x", padx=12, pady=10)

        self.pages: Dict[str, Page] = {}
        self.buttons: Dict[str, ctk.CTkButton] = {}

        self.container = ctk.CTkFrame(self.content, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        # Create pages
        self.pages["setup"] = SetupPage(self.container, self)
        self.pages["home"] = HomePage(self.container, self)
        self.pages["expenses"] = ExpensesPage(self.container, self)
        self.pages["debts"] = DebtsPage(self.container, self)
        self.pages["calc"] = CalcPage(self.container, self)
        self.pages["settings"] = SettingsPage(self.container, self)

        for p in self.pages.values():
            p.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Nav buttons
        self._nav_button("Home", "home")
        self._nav_button("Expenses", "expenses")
        self._nav_button("Debts", "debts")
        self._nav_button("Calculations", "calc")
        self._nav_button("Settings", "settings")

        # Exit
        ctk.CTkButton(self.sidebar, text="Exit", height=44, fg_color="#DC3545", hover_color="#C82333",
                      command=self.destroy).pack(side="bottom", padx=18, pady=18, fill="x")

        # Setup logic
        if self.needs_setup():
            self.disable_nav()
            self.show("setup")
        else:
            self.enable_nav()
            self.show("home")

    def _nav_button(self, text: str, key: str):
        b = ctk.CTkButton(self.nav, text=text, height=44, anchor="w",
                          command=lambda: self.show(key))
        b.pack(fill="x", padx=6, pady=6)
        self.buttons[key] = b

    def show(self, key: str):
        self.pages[key].refresh()
        self.pages[key].tkraise()

    def reload_data(self):
        self.data = ensure_settings_defaults(read_raw_save())

    def needs_setup(self) -> bool:
        if not SAVE_FILE.exists():
            return True
        p = get_path()
        # first setup should show if missing folder path
        return not p or not Path(p).exists()

    def disable_nav(self):
        for b in self.buttons.values():
            b.configure(state="disabled")

    def enable_nav(self):
        for b in self.buttons.values():
            b.configure(state="normal")


# -----------------------------
# Entry point
# -----------------------------
if __name__ == "__main__":
    ensure_save_exists()

    # Apply appearance + theme from save.json
    d = ensure_settings_defaults(read_raw_save())
    ctk.set_appearance_mode(d["Settings"]["appearance_mode"].lower())
    ctk.set_default_color_theme(d["Settings"]["color_theme"].lower())

    App().mainloop()
