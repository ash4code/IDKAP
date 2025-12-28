import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageOps
import json
import os
import shutil
import sys
import webbrowser
from datetime import datetime

# ReportLab Imports
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.lib.units import mm
from reportlab.graphics import renderPDF, renderPM

# ============================================================
# === PYINSTALLER FIX: EXPLICIT IMPORTS ===
# ============================================================
try:
    from reportlab.graphics.barcode import code128
    from reportlab.graphics.barcode import code93
    from reportlab.graphics.barcode import code39
    from reportlab.graphics.barcode import usps
    from reportlab.graphics.barcode import usps4s
    from reportlab.graphics.barcode import ecc200datamatrix
    from reportlab.graphics.barcode import eanbc
    from reportlab.graphics.barcode import qr
    from reportlab.graphics.barcode import common
except ImportError:
    pass


# ============================================================

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# --- Configuration ---
ASSETS_DIR = resource_path("assets")
PHOTOS_DIR = "photos"
PDF_DIR = "generated_pdfs"
HISTORY_FILE = "history.json"
AUDIT_FILE = "audit_log.json"

# Colors
BG_APP = "#eaeff2"
BG_SIDEBAR = "#2c3e50"
ACCENT_COLOR = "#0078d7"

# PDF Colors
COLOR_NAME = "#002944"
COLOR_POSITION = "#0071bc"
COLOR_DETAILS = "#0071bc"
COLOR_BARCODE = "#000000"

# File Paths
TEMPLATE_PATH = os.path.join(ASSETS_DIR, "template.png")
LOGO_PATH = os.path.join(ASSETS_DIR, "logo.png")
PLACEHOLDER_PATH = os.path.join(ASSETS_DIR, "placeholder.png")
DEACTIVATED_PATH = os.path.join(ASSETS_DIR, "deactivated.png")
APP_ICON_PATH = os.path.join(ASSETS_DIR, "app_icon.ico")
FONT_BOLD_PATH = os.path.join(ASSETS_DIR, "Lexend-Bold.ttf")
FONT_SEMIBOLD_PATH = os.path.join(ASSETS_DIR, "Lexend-SemiBold.ttf")

# Dimensions
CARD_WIDTH = 591
CARD_HEIGHT = 1004
LOGO_WIDTH = 591
LOGO_HEIGHT = 100
PHOTO_CORNER_RADIUS = 40
PHOTO_STROKE_WIDTH = 6
PHOTO_STROKE_COLOR = "#f08239"

if not os.path.exists(PHOTOS_DIR): os.makedirs(PHOTOS_DIR)
if not os.path.exists(PDF_DIR): os.makedirs(PDF_DIR)


def register_custom_fonts():
    fonts_ready = False
    try:
        if os.path.exists(FONT_BOLD_PATH):
            pdfmetrics.registerFont(TTFont('Lexend-Bold', FONT_BOLD_PATH))
        if os.path.exists(FONT_SEMIBOLD_PATH):
            pdfmetrics.registerFont(TTFont('Lexend-SemiBold', FONT_SEMIBOLD_PATH))
        fonts_ready = True
    except Exception:
        pass
    return fonts_ready


def make_rounded_photo_with_border(img, radius, border_w, border_color_hex):
    img = img.convert("RGBA")
    mask = Image.new('L', img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), img.size], radius=radius, fill=255)
    rounded_img = Image.new('RGBA', img.size)
    rounded_img.paste(img, (0, 0), mask=mask)
    border_overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    border_draw = ImageDraw.Draw(border_overlay)
    inset = border_w / 2
    border_draw.rounded_rectangle([(inset, inset), (img.size[0] - inset, img.size[1] - inset)], radius=radius,
                                  outline=border_color_hex, width=border_w)
    return Image.alpha_composite(rounded_img, border_overlay)


class IDCardGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ID Card Generator - IDKAP")

        if os.path.exists(APP_ICON_PATH):
            try:
                self.root.iconbitmap(APP_ICON_PATH)
            except Exception:
                pass

        self.root.state('zoomed')

        # Variables
        self.var_name = tk.StringVar()
        self.var_position = tk.StringVar()
        self.var_emp_id = tk.StringVar()
        self.var_email = tk.StringVar()
        self.var_phone = tk.StringVar()
        self.var_area = tk.StringVar()
        self.var_barcode_text = tk.StringVar()
        self.var_deactivated = tk.StringVar()
        self.var_radio_status = tk.StringVar(value="No")
        self.var_deact_reason = tk.StringVar()
        self.var_created_at = tk.StringVar()
        self.var_search = tk.StringVar()

        self.fonts_loaded = register_custom_fonts()
        self.current_photo_path = None
        self.selected_history_index = None
        self.photo_changed = False

        self.history_data = self.load_history()
        self.audit_data = self.load_audit_log()

        # Layout
        self.left_frame = tk.Frame(root, bg=BG_SIDEBAR, width=500)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        self.left_frame.pack_propagate(False)

        self.center_frame = tk.Frame(root, bg=BG_APP)
        self.center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.right_frame = tk.Frame(root, bg="white", width=500)
        self.right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        self.right_frame.pack_propagate(False)

        self.setup_ui()
        self.setup_control_area()

        # Data Handling

    def load_audit_log(self):
        if os.path.exists(AUDIT_FILE):
            try:
                with open(AUDIT_FILE, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []

    def save_audit_log_to_file(self):
        with open(AUDIT_FILE, 'w') as f: json.dump(self.audit_data, f, indent=4)

    def log_action(self, emp_id, field, old_val, new_val):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if field == "Created":
            change_text = "New Record Created"
        elif field == "Status":
            change_text = new_val
        elif field == "Photo":
            change_text = f"{old_val} -> {new_val}"
        else:
            change_text = f"'{old_val}' -> '{new_val}'"

        entry = {"emp_id": emp_id, "field": field, "change_text": change_text, "time": timestamp}
        self.audit_data.insert(0, entry)
        self.save_audit_log_to_file()
        self.refresh_audit_tab(emp_id)

    def load_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []

    def save_history_to_file(self):
        with open(HISTORY_FILE, 'w') as f: json.dump(self.history_data, f, indent=4)

    # Preview System
    def setup_ui(self):
        tk.Label(self.left_frame, text="Live Preview", font=("Segoe UI", 18, "bold"),
                 bg=BG_SIDEBAR, fg="white").pack(pady=(30, 15))
        self.scale = 0.4
        self.pv_w = int(CARD_WIDTH * self.scale)
        self.pv_h = int(CARD_HEIGHT * self.scale)
        self.preview_canvas = tk.Canvas(self.left_frame, width=self.pv_w, height=self.pv_h,
                                        bg=BG_SIDEBAR, highlightthickness=0)
        self.preview_canvas.pack(pady=10, padx=20)
        self.left_frame.bind("<Configure>", self.on_frame_configure)

    def on_frame_configure(self, event):
        available_w = event.width - 60
        if available_w <= 0: return
        new_scale = available_w / CARD_WIDTH
        new_scale = max(0.3, min(new_scale, 1.2))
        if abs(self.scale - new_scale) > 0.01:
            self.scale = new_scale
            self.pv_w = int(CARD_WIDTH * self.scale)
            self.pv_h = int(CARD_HEIGHT * self.scale)
            self.preview_canvas.config(width=self.pv_w, height=self.pv_h)
            self.update_preview()

    def update_preview(self, *args):
        def s(val):
            return int(val * self.scale)

        try:
            if os.path.exists(TEMPLATE_PATH):
                base_img = Image.open(TEMPLATE_PATH).resize((self.pv_w, self.pv_h), Image.LANCZOS).convert("RGBA")
            else:
                base_img = Image.new('RGB', (self.pv_w, self.pv_h), color=(255, 255, 255))

            if os.path.exists(LOGO_PATH):
                logo_img = Image.open(LOGO_PATH)
                logo_w, logo_h = int(LOGO_WIDTH * self.scale), int(LOGO_HEIGHT * self.scale)
                logo_img = logo_img.resize((logo_w, logo_h), Image.LANCZOS)
                base_img.paste(logo_img, (0, s(50)), logo_img.convert("RGBA"))

            photo_p = self.current_photo_path if (
                        self.current_photo_path and os.path.exists(self.current_photo_path)) else PLACEHOLDER_PATH
            if os.path.exists(photo_p):
                u_img = Image.open(photo_p)
                pb_w, pb_h = s(300), s(350)
                pb_x, pb_y = s(145), s(180)
                u_img = ImageOps.fit(u_img, (pb_w, pb_h), centering=(0.5, 0.5))
                rad = s(PHOTO_CORNER_RADIUS)
                bor = max(1, s(PHOTO_STROKE_WIDTH))
                u_img_styled = make_rounded_photo_with_border(u_img, rad, bor, PHOTO_STROKE_COLOR)
                base_img.paste(u_img_styled, (pb_x, pb_y), u_img_styled)

            self.tk_image = ImageTk.PhotoImage(base_img.convert("RGB"))
            self.preview_canvas.delete("all")
            self.preview_canvas.create_image(self.pv_w // 2, self.pv_h // 2, image=self.tk_image)

            self.preview_canvas.create_text(self.pv_w // 2, s(560), text=self.var_name.get() or "Name Here",
                                            font=("Arial", s(42), "bold"), fill=COLOR_NAME)
            self.preview_canvas.create_text(self.pv_w // 2, s(600), text=self.var_position.get() or "Position",
                                            font=("Arial", s(22), "bold"), fill=COLOR_POSITION)
            self.preview_canvas.create_text(self.pv_w // 2, s(655), text="Employee Details",
                                            font=("Arial", s(18), "bold"), fill=COLOR_NAME)

            self.preview_canvas.create_text(s(80), s(685), text="Employee ID\nEmail\nPhone No\nOperation Area",
                                            font=("Arial", s(14), "bold"), anchor="nw", fill=COLOR_NAME)
            self.preview_canvas.create_text(s(230), s(685), text=":\n:\n:\n:", font=("Arial", s(14), "bold"),
                                            anchor="nw", fill=COLOR_NAME)
            details_text = f"{self.var_emp_id.get() or 'ID'}\n{self.var_email.get() or 'Email'}\n{self.var_phone.get() or 'Phone'}\n{self.var_area.get() or 'Area'}"
            self.preview_canvas.create_text(s(250), s(685), text=details_text, font=("Arial", s(14), "bold"),
                                            anchor="nw", fill=COLOR_DETAILS)

            # Barcode Preview
            bc_val = self.var_barcode_text.get() or "123456789"
            if bc_val:
                try:
                    d = createBarcodeDrawing('Code128', value=bc_val, barHeight=15 * mm * self.scale, barWidth=1.0)
                    bc_pil = renderPM.drawToPIL(d, dpi=72, bg=0xf1f1f1)
                    self.tk_bc_img = ImageTk.PhotoImage(bc_pil)
                    self.preview_canvas.create_image(self.pv_w // 2, s(830), image=self.tk_bc_img)
                    self.preview_canvas.create_text(self.pv_w // 2, s(860), text=bc_val, font=("Arial", s(12)),
                                                    fill=COLOR_BARCODE)
                except:
                    pass

            if self.var_deactivated.get() and os.path.exists(DEACTIVATED_PATH):
                d_img = Image.open(DEACTIVATED_PATH).convert("RGBA")
                target_w = int(self.pv_w * 0.8)
                aspect = d_img.height / d_img.width
                d_img = d_img.resize((target_w, int(target_w * aspect)), Image.LANCZOS)
                self.tk_stamp = ImageTk.PhotoImage(d_img)
                self.preview_canvas.create_image(self.pv_w // 2, self.pv_h // 2, image=self.tk_stamp)
                self.preview_canvas.create_text(self.pv_w // 2, s(885), text=f"EXP: {self.var_deactivated.get()}",
                                                font=("Arial", s(20), "bold"), fill="#630402")
        except Exception:
            pass

    # Control Area
    def setup_control_area(self):
        c_canvas = tk.Canvas(self.center_frame, bg=BG_APP, highlightthickness=0)
        c_scrollbar = ttk.Scrollbar(self.center_frame, orient="vertical", command=c_canvas.yview)
        c_scrollable = tk.Frame(c_canvas, bg=BG_APP)
        c_window_id = c_canvas.create_window((0, 0), window=c_scrollable, anchor="nw")

        def on_canvas_configure(event):
            c_canvas.itemconfig(c_window_id, width=event.width)

        c_canvas.bind('<Configure>', on_canvas_configure)
        c_scrollable.bind("<Configure>", lambda e: c_canvas.configure(scrollregion=c_canvas.bbox("all")))
        c_canvas.configure(yscrollcommand=c_scrollbar.set)

        c_canvas.pack(side="left", fill="both", expand=True)
        c_scrollbar.pack(side="right", fill="y")

        tk.Label(c_scrollable, text="Employee Management Dashboard", font=("Segoe UI", 20, "bold"),
                 bg=BG_APP, fg="#333").pack(anchor="w", padx=20, pady=(20, 20))

        # === 1. FORM & PHOTO ===
        form_frame = tk.LabelFrame(c_scrollable, text="  New Entry Form  ", bg=BG_APP, font=("Segoe UI", 11, "bold"),
                                   padx=15, pady=15)
        form_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

        # Row 1
        tk.Label(form_frame, text="Full Name", bg=BG_APP).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(form_frame, textvariable=self.var_name).grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 10))

        tk.Label(form_frame, text="Job Position", bg=BG_APP).grid(row=0, column=1, sticky="w", padx=5, pady=2)
        ttk.Entry(form_frame, textvariable=self.var_position).grid(row=1, column=1, sticky="ew", padx=5, pady=(0, 10))

        # Row 2
        tk.Label(form_frame, text="Employee ID", bg=BG_APP).grid(row=2, column=0, sticky="w", padx=5, pady=2)

        # --- ID ENTRY Widget Saved to Self for Locking ---
        self.ent_id = ttk.Entry(form_frame, textvariable=self.var_emp_id)
        self.ent_id.grid(row=3, column=0, sticky="ew", padx=5, pady=(0, 10))

        tk.Label(form_frame, text="Email Address", bg=BG_APP).grid(row=2, column=1, sticky="w", padx=5, pady=2)
        ttk.Entry(form_frame, textvariable=self.var_email).grid(row=3, column=1, sticky="ew", padx=5, pady=(0, 10))

        # Row 3
        tk.Label(form_frame, text="Phone Number", bg=BG_APP).grid(row=4, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(form_frame, textvariable=self.var_phone).grid(row=5, column=0, sticky="ew", padx=5, pady=(0, 10))

        tk.Label(form_frame, text="Area/Branch", bg=BG_APP).grid(row=4, column=1, sticky="w", padx=5, pady=2)
        ttk.Entry(form_frame, textvariable=self.var_area).grid(row=5, column=1, sticky="ew", padx=5, pady=(0, 10))

        # Row 4 (Barcode LEFT, Photo Button RIGHT)
        tk.Label(form_frame, text="Barcode Value", bg=BG_APP).grid(row=6, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(form_frame, textvariable=self.var_barcode_text).grid(row=7, column=0, sticky="ew", padx=5,
                                                                       pady=(0, 10))

        # --- PHOTO BUTTON ---
        tk.Label(form_frame, text="Profile Image", bg=BG_APP).grid(row=6, column=1, sticky="w", padx=5, pady=2)
        tk.Button(form_frame, text="UPLOAD PHOTO", command=self.upload_photo,
                  bg="#0078d7", fg="white", font=("Segoe UI", 9, "bold"), cursor="hand2").grid(row=7, column=1,
                                                                                               sticky="ew", padx=5,
                                                                                               pady=(0, 10), ipady=5)

        form_frame.columnconfigure(0, weight=1)
        form_frame.columnconfigure(1, weight=1)

        for v in [self.var_name, self.var_position, self.var_emp_id, self.var_email, self.var_phone, self.var_area,
                  self.var_barcode_text]:
            v.trace_add("write", self.update_preview)

        # Actions
        action_frame = tk.Frame(c_scrollable, bg=BG_APP)
        action_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

        status_box = tk.LabelFrame(action_frame, text="  Account Status & Reason  ", bg=BG_APP, padx=10, pady=10)
        status_box.pack(fill=tk.X)

        self.ent_reason = ttk.Entry(status_box, textvariable=self.var_deact_reason, state='disabled', width=30)

        def on_radio_click():
            if self.var_radio_status.get() == "Yes":
                if not self.var_deactivated.get(): self.var_deactivated.set(datetime.now().strftime("%Y-%m-%d"))
                self.ent_reason.config(state='normal')
            else:
                self.var_deactivated.set("")
                self.var_deact_reason.set("")
                self.ent_reason.config(state='disabled')
            self.update_preview()

        tk.Radiobutton(status_box, text="Active", variable=self.var_radio_status, value="No", command=on_radio_click,
                       bg=BG_APP).pack(side=tk.LEFT, padx=10)
        tk.Radiobutton(status_box, text="Deactivated", variable=self.var_radio_status, value="Yes",
                       command=on_radio_click, bg=BG_APP, fg="red").pack(side=tk.LEFT, padx=10)

        tk.Label(status_box, textvariable=self.var_deactivated, bg=BG_APP, fg="#666", width=12).pack(side=tk.LEFT,
                                                                                                     padx=5)
        tk.Label(status_box, text="Reason:", bg=BG_APP).pack(side=tk.LEFT, padx=(10, 5))
        self.ent_reason.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Buttons
        btn_box = tk.Frame(c_scrollable, bg=BG_APP)
        btn_box.pack(fill=tk.X, padx=20, pady=(0, 30))
        tk.Button(btn_box, text="SAVE RECORD", command=self.save_data, bg="#28a745", fg="white",
                  font=("Segoe UI", 9, "bold"), width=15, height=2, relief="flat").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_box, text="CLEAR", command=self.clear_form, bg="#dc3545", fg="white",
                  font=("Segoe UI", 9, "bold"), width=12, height=2, relief="flat").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_box, text="PRINT PDF", command=self.generate_pdf, bg="#343a40", fg="white",
                  font=("Segoe UI", 9, "bold"), width=12, height=2, relief="flat").pack(side=tk.LEFT, padx=5)

        # Database
        list_frame = tk.LabelFrame(c_scrollable, text="  Database  ", bg=BG_APP, font=("Segoe UI", 11, "bold"), padx=10,
                                   pady=10)
        list_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

        search_row = tk.Frame(list_frame, bg=BG_APP)
        search_row.pack(fill=tk.X, pady=(0, 10))
        tk.Label(search_row, text="Search:", bg=BG_APP).pack(side=tk.LEFT)
        ttk.Entry(search_row, textvariable=self.var_search).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        self.var_search.trace_add("write", self.filter_history)
        tk.Button(search_row, text="EDIT SELECTED ROW", command=self.load_from_history,
                  bg="#007bff", fg="white", relief="flat", font=("Segoe UI", 8)).pack(side=tk.RIGHT)

        table_container = tk.Frame(list_frame)
        table_container.pack(fill=tk.X)
        tree_scroll = ttk.Scrollbar(table_container)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        cols = ("id", "name", "position", "email", "phone", "area")
        self.tree = ttk.Treeview(table_container, columns=cols, show="headings", height=8,
                                 yscrollcommand=tree_scroll.set)
        tree_scroll.config(command=self.tree.yview)
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=100)
        self.tree.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.refresh_history_list()

        # Footer
        footer_frame = tk.Frame(c_scrollable, bg=BG_APP, pady=20)
        footer_frame.pack(fill=tk.X)
        tk.Label(footer_frame, text="Developed by Ash & Gemini | Open Source Project",
                 font=("Segoe UI", 9), bg=BG_APP, fg="#999").pack()
        tk.Label(footer_frame, text="v1.0.0 (github.com/ash4code)",
                 font=("Segoe UI", 8), bg=BG_APP, fg="#bbb").pack()

        # Audit Log
        r_header = tk.Frame(self.right_frame, bg="white", pady=10, padx=20)
        r_header.pack(fill=tk.X)
        tk.Label(r_header, text="Activity Log", font=("Segoe UI", 16, "bold"), bg="white", fg="#333").pack(anchor="w")
        self.lbl_audit_header = tk.Label(r_header, text="(Select an ID to view)", font=("Segoe UI", 9), bg="white",
                                         fg="#999")
        self.lbl_audit_header.pack(anchor="w")

        header_row = tk.Frame(self.right_frame, bg="#f1f1f1", pady=5)
        header_row.pack(fill=tk.X)
        tk.Label(header_row, text="Field", width=12, bg="#f1f1f1", font=("Segoe UI", 9, "bold"), anchor="w").pack(
            side=tk.LEFT, padx=(20, 0))
        tk.Label(header_row, text="Change (Old -> New)", bg="#f1f1f1", font=("Segoe UI", 9, "bold"), anchor="w").pack(
            side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(header_row, text="Time", width=18, bg="#f1f1f1", font=("Segoe UI", 9, "bold"), anchor="e").pack(
            side=tk.RIGHT, padx=(0, 20))

        log_container = tk.Frame(self.right_frame, bg="white")
        log_container.pack(fill=tk.BOTH, expand=True)

        self.audit_canvas = tk.Canvas(log_container, bg="white", highlightthickness=0)
        self.audit_scrollbar = ttk.Scrollbar(log_container, orient="vertical", command=self.audit_canvas.yview)
        self.audit_scrollable_frame = tk.Frame(self.audit_canvas, bg="white")

        self.audit_scrollable_frame.bind("<Configure>", lambda e: self.audit_canvas.configure(
            scrollregion=self.audit_canvas.bbox("all")))
        self.audit_window = self.audit_canvas.create_window((0, 0), window=self.audit_scrollable_frame, anchor="nw")

        def on_audit_resize(event):
            self.audit_canvas.itemconfig(self.audit_window, width=event.width)

        self.audit_canvas.bind("<Configure>", on_audit_resize)
        self.audit_canvas.configure(yscrollcommand=self.audit_scrollbar.set)

        self.audit_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.audit_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.refresh_audit_tab(None)

    def refresh_audit_tab(self, emp_id=None):
        for widget in self.audit_scrollable_frame.winfo_children(): widget.destroy()
        if not emp_id:
            self.lbl_audit_header.config(text="(Select an ID to view)")
            return

        self.lbl_audit_header.config(text=f"History for ID: {emp_id}")
        user_logs = [x for x in self.audit_data if str(x.get("emp_id")) == str(emp_id)]

        for item in user_logs:
            row_frame = tk.Frame(self.audit_scrollable_frame, bg="white", pady=5)
            row_frame.pack(fill=tk.X, padx=10)
            fg_col = "blue" if item["field"] == "Created" else "red" if item["field"] == "Status" else "#333"

            tk.Label(row_frame, text=item["field"], width=10, anchor="nw", fg=fg_col, bg="white",
                     font=("Segoe UI", 11)).pack(side=tk.LEFT)
            tk.Label(row_frame, text=item["time"], width=18, anchor="ne", fg="#888", bg="white",
                     font=("Segoe UI", 9)).pack(side=tk.RIGHT)

            # --- FIXED TEXT WRAPPING WIDTH (250px so it doesn't get cut off) ---
            tk.Label(row_frame, text=item["change_text"], anchor="w", justify="left", wraplength=250, bg="white",
                     font=("Segoe UI", 11)).pack(side=tk.LEFT, fill=tk.X, expand=True)

            tk.Frame(self.audit_scrollable_frame, height=1, bg="#eee").pack(fill=tk.X, padx=10, pady=(0, 5))

    def upload_photo(self):
        f = filedialog.askopenfilename(filetypes=[("Images", "*.jpg *.png *.jpeg")])
        if f:
            self.current_photo_path = f
            self.photo_changed = True
            self.update_preview()

    def save_data(self):
        emp_id = self.var_emp_id.get()
        if not emp_id: return messagebox.showerror("Error", "Employee ID required")

        final_photo_path = ""
        if self.current_photo_path and os.path.exists(self.current_photo_path):
            ext = os.path.splitext(self.current_photo_path)[1]
            fname = f"{emp_id}{ext}"
            final_photo_path = os.path.join(PHOTOS_DIR, fname)
            try:
                shutil.copy(self.current_photo_path, final_photo_path)
            except:
                pass

        if not self.var_created_at.get():
            self.var_created_at.set(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        new_record = {
            "name": self.var_name.get(), "position": self.var_position.get(),
            "emp_id": emp_id, "email": self.var_email.get(),
            "phone": self.var_phone.get(), "area": self.var_area.get(),
            "barcode": self.var_barcode_text.get(),
            "deactivated_date": self.var_deactivated.get(),
            "deactivation_reason": self.var_deact_reason.get(),
            "created_at": self.var_created_at.get(),
            "photo": final_photo_path
        }

        if self.selected_history_index is not None:
            # === FULL CHANGE TRACKING ===
            old_record = self.history_data[self.selected_history_index]

            # 1. Track Status Change
            old_deact = old_record.get("deactivated_date", "")
            new_deact = new_record["deactivated_date"]
            if old_deact != new_deact:
                if new_deact:
                    reason = new_record.get("deactivation_reason", "")
                    self.log_action(emp_id, "Status", "Active", f"Deactivated ({new_deact}) - Reason: {reason}")
                else:
                    self.log_action(emp_id, "Status", "Deactivated", "Reactivated")

            # 2. Track Photo Change
            if self.photo_changed:
                self.log_action(emp_id, "Photo", "Previous", "Updated")

            # 3. Track ALL Other Fields
            check_fields = [("Name", "name"), ("Position", "position"), ("Email", "email"),
                            ("Phone", "phone"), ("Area", "area"), ("Barcode", "barcode")]

            for label, key in check_fields:
                if old_record.get(key) != new_record.get(key):
                    self.log_action(emp_id, label, old_record.get(key, ""), new_record.get(key, ""))

            self.history_data[self.selected_history_index] = new_record
        else:
            self.history_data.append(new_record)
            self.log_action(emp_id, "Created", "", "")

        self.save_history_to_file()
        self.refresh_history_list()
        self.clear_form()
        self.refresh_audit_tab(emp_id)
        messagebox.showinfo("Saved", "Record saved successfully.")

    def clear_form(self):
        for v in [self.var_name, self.var_position, self.var_emp_id, self.var_email, self.var_phone, self.var_area,
                  self.var_barcode_text, self.var_deactivated, self.var_created_at, self.var_deact_reason]:
            v.set("")
        self.var_radio_status.set("No")
        self.ent_reason.config(state='disabled')

        # UNLOCK ID FIELD for new entries
        if hasattr(self, 'ent_id'):
            self.ent_id.config(state='normal')

        self.current_photo_path = None
        self.selected_history_index = None
        self.photo_changed = False
        self.var_search.set("")
        self.update_preview()

    def filter_history(self, *args):
        q = self.var_search.get().lower()
        res = [x for x in self.history_data if q in x.get("emp_id", "").lower() or q in x.get("phone", "").lower()]
        self.refresh_history_list(res)

    def refresh_history_list(self, data=None):
        self.tree.delete(*self.tree.get_children())
        d = data if data else self.history_data
        for i in d:
            self.tree.insert("", tk.END, values=(i.get("emp_id", ""), i.get("name", ""), i.get("position", ""),
                                                 i.get("email", ""), i.get("phone", ""), i.get("area", "")))

    def load_from_history(self):
        sel = self.tree.selection()
        if not sel: return
        val = self.tree.item(sel[0])['values'][0]
        for idx, item in enumerate(self.history_data):
            if str(item["emp_id"]) == str(val):
                self.selected_history_index = idx
                self.var_name.set(item["name"])
                self.var_position.set(item["position"])
                self.var_emp_id.set(item["emp_id"])

                # LOCK ID FIELD when editing
                if hasattr(self, 'ent_id'):
                    self.ent_id.config(state='disabled')

                self.var_email.set(item["email"])
                self.var_phone.set(item["phone"])
                self.var_area.set(item["area"])
                self.var_barcode_text.set(item.get("barcode", ""))

                d_date = item.get("deactivated_date", "")
                self.var_deactivated.set(d_date)
                self.var_radio_status.set("Yes" if d_date else "No")

                reason = item.get("deactivation_reason", "")
                self.var_deact_reason.set(reason)
                if d_date:
                    self.ent_reason.config(state='normal')
                else:
                    self.ent_reason.config(state='disabled')

                self.var_created_at.set(item.get("created_at", ""))
                self.current_photo_path = item["photo"] if os.path.exists(item.get("photo", "")) else None
                self.photo_changed = False
                self.update_preview()
                self.refresh_audit_tab(val)
                break

    def generate_pdf(self):
        if not self.var_emp_id.get(): return messagebox.showerror("Error", "ID required")
        path = os.path.join(PDF_DIR, f"{self.var_emp_id.get()}.pdf")
        c = canvas.Canvas(path, pagesize=(CARD_WIDTH, CARD_HEIGHT))
        font_main = "Lexend-Bold" if self.fonts_loaded else "Helvetica-Bold"
        font_sub = "Lexend-SemiBold" if self.fonts_loaded else "Helvetica"
        if os.path.exists(TEMPLATE_PATH): c.drawImage(TEMPLATE_PATH, 0, 0, width=CARD_WIDTH, height=CARD_HEIGHT)
        if os.path.exists(LOGO_PATH): c.drawImage(LOGO_PATH, 0, CARD_HEIGHT - LOGO_HEIGHT - 50, width=LOGO_WIDTH,
                                                  height=LOGO_HEIGHT, mask='auto')

        photo_w, photo_h = 300, 350
        photo_x, photo_y = (CARD_WIDTH - photo_w) / 2, 500
        p_path = self.current_photo_path if (
                    self.current_photo_path and os.path.exists(self.current_photo_path)) else PLACEHOLDER_PATH
        try:
            pr = ImageReader(p_path)
            iw, ih = pr.getSize()
            aspect = iw / ih
            draw_w, draw_h = photo_w, photo_w / aspect
            if draw_h > photo_h: draw_h, draw_w = photo_h, photo_h * aspect
            dx, dy = photo_x + (photo_w - draw_w) / 2, photo_y + (photo_h - draw_h) / 2
            c.saveState()
            path_obj = c.beginPath()
            path_obj.roundRect(dx, dy, draw_w, draw_h, PHOTO_CORNER_RADIUS)
            c.clipPath(path_obj, stroke=0, fill=0)
            c.drawImage(pr, dx, dy, width=draw_w, height=draw_h, mask='auto')
            c.restoreState()
            r, g, b = int(PHOTO_STROKE_COLOR[1:3], 16) / 255.0, int(PHOTO_STROKE_COLOR[3:5], 16) / 255.0, int(
                PHOTO_STROKE_COLOR[5:7], 16) / 255.0
            c.setStrokeColorRGB(r, g, b)
            c.setLineWidth(PHOTO_STROKE_WIDTH)
            c.roundRect(dx, dy, draw_w, draw_h, PHOTO_CORNER_RADIUS, stroke=1, fill=0)
        except:
            pass

        c.setFillColor(HexColor(COLOR_NAME))
        c.setFont(font_main, 61)
        c.drawCentredString(CARD_WIDTH / 2, 420, self.var_name.get())
        c.setFillColor(HexColor(COLOR_POSITION))
        c.setFont(font_sub, 32)
        c.drawCentredString(CARD_WIDTH / 2, 385, self.var_position.get())
        c.setFillColor(HexColor(COLOR_NAME))
        c.setFont(font_main, 25)
        c.drawCentredString(CARD_WIDTH / 2, 330, "Employee Details")

        labels = [("Employee ID", 288), ("Email", 266), ("Phone No", 243), ("Operation Area", 221)]
        for txt, y in labels:
            c.setFillColor(HexColor(COLOR_NAME))
            c.setFont(font_sub, 18)
            c.drawCentredString(130 if "ID" in txt else 96 if "Email" in txt else 114 if "Phone" in txt else 140, y,
                                txt)
            c.drawCentredString(222, y, ":")

        start_y = 288
        for val in [self.var_emp_id.get(), self.var_email.get(), self.var_phone.get(), self.var_area.get()]:
            c.setFillColor(HexColor(COLOR_DETAILS))
            c.setFont(font_sub, 18)
            c.drawString(240, start_y, str(val))
            start_y -= 22

        # Barcode Logic
        bc_val = self.var_barcode_text.get()
        if bc_val:
            try:
                d = createBarcodeDrawing('Code128', value=bc_val, barHeight=12 * mm, barWidth=1.5)
                bc_x = (CARD_WIDTH - d.width) / 2
                renderPDF.draw(d, c, bc_x, 165)
                c.setFillColor(HexColor(COLOR_BARCODE))
                c.setFont(font_sub, 14)
                c.drawCentredString(CARD_WIDTH / 2, 150, bc_val)
            except:
                pass

        if self.var_deactivated.get() and os.path.exists(DEACTIVATED_PATH):
            try:
                d_reader = ImageReader(DEACTIVATED_PATH)
                iw, ih = d_reader.getSize()
                aspect = ih / iw
                stamp_w = 500
                stamp_h = stamp_w * aspect
                c.drawImage(DEACTIVATED_PATH, (CARD_WIDTH - stamp_w) / 2, (CARD_HEIGHT - stamp_h) / 2, width=stamp_w,
                            height=stamp_h, mask='auto')
                c.setFillColor(HexColor("#630402"))
                c.setFont(font_main, 24)
                c.drawCentredString(CARD_WIDTH / 2, 120, f"EXP DATE: {self.var_deactivated.get()}")
            except:
                pass

        c.save()
        messagebox.showinfo("Success", f"PDF Created: {path}")


if __name__ == "__main__":
    root = tk.Tk()
    app = IDCardGeneratorApp(root)
    root.mainloop()