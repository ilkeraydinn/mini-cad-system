# main.py
import tkinter as tk
from tkinter import colorchooser, filedialog, ttk, messagebox
import json
import math
import copy

from config import COLORS, FONTS
import math_3d
import ui_utils

class MiniCADApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mini CAD System")
        self.root.geometry("800x600")
        self.root.configure(bg=COLORS["bg"])

        # --- UYGULAMA DURUM DEĞİŞKENLERİ ---
        self.current_tool = "rectangle"
        self.start_x = None
        self.start_y = None
        
        self.cam_rot_x = 0.0
        self.cam_rot_y = 0.0
        self.right_start_x = None
        self.right_start_y = None
        
        self.temp_item = None
        self.selected_item = None
        self.dragging_handle = None
        self.init_coords = None
        
        self.current_color = "#3b82f6"
        self.style_mode = tk.StringVar(value="fill")
        self.line_width = tk.IntVar(value=2)
        
        self.show_grid = tk.BooleanVar(value=True)
        self.snap_grid = tk.BooleanVar(value=False)
        self.grid_size = 20
        
        self.history = []
        self.redo_history = []
        self.id_counter = 0

        # --- 3D RENDER DEĞİŞKENLERİ ---
        self.objects_3d = []
        self.light_dir = [0.577, -0.577, 0.577]
        self.is_rotating = False
        self.is_creating_3d = False

        # --- TTK STİLİ ---
        style = ttk.Style()
        if 'clam' in style.theme_names():
            style.theme_use('clam')
        style.configure("Modern.TCheckbutton",
            background=COLORS["edit_bar"], foreground=COLORS["text"],
            font=FONTS["normal"], focuscolor=COLORS["edit_bar"])
        style.map("Modern.TCheckbutton",
            background=[("active", COLORS["edit_bar"])])

        self.setup_ui()
        self.setup_canvas()

    def setup_ui(self):
        # 1. ANA ARAÇ ÇUBUĞU
        self.toolbar = tk.Frame(self.root, bg=COLORS["toolbar"], highlightbackground=COLORS["border"], highlightthickness=1, height=52)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)
        self.toolbar.pack_propagate(False)

        ui_utils.make_btn(self.toolbar, "▶  Seç", lambda: self.select_tool("select"), bg=COLORS["sel"], fg=COLORS["sel_fg"], hbg=COLORS["sel_hover"], font=FONTS["bold"], padx=12, pady=6, px=6, py=7)
        ui_utils.sep(self.toolbar, COLORS["toolbar"])

        tk.Label(self.toolbar, text="2D", bg=COLORS["toolbar"], fg=COLORS["muted"], font=FONTS["small"]).pack(side=tk.LEFT, padx=(2,1))
        for label, tool in [("Çizgi","line"), ("Dikdörtgen","rectangle"), ("Üçgen","triangle"), ("Daire","circle")]:
            ui_utils.make_btn(self.toolbar, label, lambda t=tool: self.select_tool(t), padx=10, pady=6)
        ui_utils.sep(self.toolbar, COLORS["toolbar"])

        tk.Label(self.toolbar, text="3D", bg=COLORS["toolbar"], fg=COLORS["muted"], font=FONTS["small"]).pack(side=tk.LEFT, padx=(2,1))
        ui_utils.make_btn(self.toolbar, "⬛ Küp", lambda: self.select_tool("cube"), bg=COLORS["3d"], fg=COLORS["3d_fg"], hbg=COLORS["3d_hover"], padx=10, pady=6)
        ui_utils.make_btn(self.toolbar, "△  Piramit", lambda: self.select_tool("pyramid"), bg=COLORS["3d"], fg=COLORS["3d_fg"], hbg=COLORS["3d_hover"], padx=10, pady=6)
        ui_utils.sep(self.toolbar, COLORS["toolbar"])

        tk.Label(self.toolbar, text="Renk", bg=COLORS["toolbar"], fg=COLORS["muted"], font=FONTS["small"]).pack(side=tk.LEFT, padx=(2,2))
        self.color_btn = tk.Button(self.toolbar, text="   ●   ", bg=self.current_color, fg=self.current_color, font=("Segoe UI", 14), relief="flat", cursor="hand2", bd=0, highlightthickness=2, highlightbackground=COLORS["border"], command=self.choose_color)
        self.color_btn.pack(side=tk.LEFT, padx=4, pady=8)
        ui_utils.sep(self.toolbar, COLORS["toolbar"])

        tk.Label(self.toolbar, text="Kalınlık", bg=COLORS["toolbar"], fg=COLORS["muted"], font=FONTS["small"]).pack(side=tk.LEFT, padx=(2,2))
        self.width_cb = ttk.Combobox(self.toolbar, textvariable=self.line_width, values=[1, 2, 3, 5, 8, 10], width=3, state="readonly", font=FONTS["normal"])
        self.width_cb.pack(side=tk.LEFT, padx=4, pady=10)
        self.width_cb.bind("<<ComboboxSelected>>", lambda e: self.apply_properties_to_selected())
        ui_utils.sep(self.toolbar, COLORS["toolbar"])

        style_frame = tk.Frame(self.toolbar, bg=COLORS["toolbar"])
        style_frame.pack(side=tk.LEFT, padx=5)
        for lbl, val in [("Kenarlık","outline"),("Dolu","fill")]:
            tk.Radiobutton(style_frame, text=lbl, variable=self.style_mode, value=val, bg=COLORS["toolbar"], fg=COLORS["text"], selectcolor=COLORS["accent"], activebackground=COLORS["toolbar"], font=FONTS["normal"], command=self.apply_properties_to_selected).pack(side=tk.LEFT, padx=4)

        # 2. DÜZENLEME ÇUBUĞU
        self.edit_panel = tk.Frame(self.root, bg=COLORS["edit_bar"], highlightbackground=COLORS["border"], highlightthickness=1, height=46)
        self.edit_panel.pack(side=tk.TOP, fill=tk.X)
        self.edit_panel.pack_propagate(False)

        for lbl, var, cmd in [("⊞ Izgara", self.show_grid, self.draw_grid_lines), ("⊡ Yapış",  self.snap_grid, None)]:
            cb_cmd = cmd if cmd else (lambda: None)
            ttk.Checkbutton(self.edit_panel, text=lbl, variable=var, command=cb_cmd, style="Modern.TCheckbutton").pack(side=tk.LEFT, padx=5, pady=10)

        ui_utils.sep(self.edit_panel, COLORS["edit_bar"])
        tk.Label(self.edit_panel, text="Katman", bg=COLORS["edit_bar"], fg=COLORS["muted"], font=FONTS["small"]).pack(side=tk.LEFT, padx=(2,1))
        ui_utils.make_btn(self.edit_panel, "↑ Öne",   self.bring_front, padx=8, pady=4, py=9)
        ui_utils.make_btn(self.edit_panel, "↓ Arkaya", self.send_back, padx=8, pady=4, py=9)

        ui_utils.sep(self.edit_panel, COLORS["edit_bar"])
        tk.Label(self.edit_panel, text="Boyut", bg=COLORS["edit_bar"], fg=COLORS["muted"], font=FONTS["small"]).pack(side=tk.LEFT, padx=(2,1))
        ui_utils.make_btn(self.edit_panel, "+ Büyüt", lambda: self.scale_selected(1.2), padx=8, pady=4, py=9)
        ui_utils.make_btn(self.edit_panel, "− Küçült", lambda: self.scale_selected(0.8), padx=8, pady=4, py=9)

        ui_utils.sep(self.edit_panel, COLORS["edit_bar"])
        ui_utils.make_btn(self.edit_panel, "⧉ Kopyala", self.duplicate_item, bg=COLORS["accent"], fg=COLORS["accent_fg"], hbg=COLORS["accent_hover"], padx=9, pady=4, py=9)
        ui_utils.make_btn(self.edit_panel, "↩ Geri",    self.undo, padx=8, pady=4, py=9)
        ui_utils.make_btn(self.edit_panel, "↪ İleri",   self.redo, padx=8, pady=4, py=9)
        ui_utils.make_btn(self.edit_panel, "🗑 Sil",    self.delete_item, bg=COLORS["danger"], fg=COLORS["danger_fg"], hbg=COLORS["danger_hover"], padx=9, pady=4, py=9)

        ui_utils.sep(self.edit_panel, COLORS["edit_bar"])
        tk.Label(self.edit_panel, text="Z°", bg=COLORS["edit_bar"], fg=COLORS["muted"], font=FONTS["small"]).pack(side=tk.LEFT, padx=(2,1))
        ui_utils.make_btn(self.edit_panel, "↶ −15", lambda: self.rotate_selected(-15,'z'), padx=7, pady=4, py=9)
        ui_utils.make_btn(self.edit_panel, "↷ +15", lambda: self.rotate_selected(15,'z'), padx=7, pady=4, py=9)

        ui_utils.sep(self.edit_panel, COLORS["edit_bar"])
        tk.Label(self.edit_panel, text="3D°", bg=COLORS["edit_bar"], fg=COLORS["muted"], font=FONTS["small"]).pack(side=tk.LEFT, padx=(2,1))
        for lbl, args in [("← Y", (-15,'y')), ("→ Y", (15,'y')), ("↑ X", (-15,'x')), ("↓ X", (15,'x'))]:
            ui_utils.make_btn(self.edit_panel, lbl, lambda a=args: self.rotate_selected(*a), padx=6, pady=4, py=9)

        ui_utils.sep(self.edit_panel, COLORS["edit_bar"])
        ui_utils.make_btn(self.edit_panel, "✕ Temizle", self.clear_canvas, bg=COLORS["danger"], fg=COLORS["danger_fg"], hbg=COLORS["danger_hover"], padx=9, pady=4, py=9)
        ui_utils.make_btn(self.edit_panel, "💾 Kaydet", self.save_file, bg=COLORS["success"], fg=COLORS["success_fg"], hbg=COLORS["success_hover"], padx=9, pady=4, py=9)
        ui_utils.make_btn(self.edit_panel, "📂 Yükle",  self.load_file, bg=COLORS["info"], fg=COLORS["info_fg"], hbg=COLORS["info_hover"], padx=9, pady=4, py=9)

    def setup_canvas(self):
        self.canvas = tk.Canvas(self.root, bg=COLORS["canvas"], cursor="cross", highlightthickness=0)
        self.canvas.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

        self.canvas.bind("<Button-1>", self.on_mouse_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_release)
        
        self.canvas.bind("<Button-3>", self.on_right_press)
        self.canvas.bind("<B3-Motion>", self.on_right_drag)
        self.canvas.bind("<ButtonRelease-3>", self.on_right_release) 
        
        self.root.bind("<Control-c>", lambda e: self.duplicate_item())
        self.root.bind("<Control-C>", lambda e: self.duplicate_item())
        self.root.bind("<Delete>", lambda e: self.delete_item())
        self.root.bind("<Control-z>", self.undo)
        self.root.bind("<Control-Z>", self.undo)
        self.root.bind("<Control-y>", self.redo)
        self.root.bind("<Control-Y>", self.redo)
        
        self.draw_grid_lines()
        self.canvas.bind("<Configure>", lambda e: self.draw_grid_lines())

    def apply_properties_to_selected(self):
        if self.selected_item:
            self.save_state()
            if isinstance(self.selected_item, str) and self.selected_item.startswith("3d_"):
                obj = next((o for o in self.objects_3d if o["id"] == self.selected_item), None)
                if obj:
                    obj["color"] = self.current_color
                    obj["style"] = self.style_mode.get()
                    obj["width"] = self.line_width.get()
                    self.render_3d_objects()
            else:
                item_type = self.canvas.type(self.selected_item)
                w = self.line_width.get()
                if item_type == "line":
                    self.canvas.itemconfig(self.selected_item, fill=self.current_color, width=w)
                else:
                    fill_col = self.current_color if self.style_mode.get() == "fill" else ""
                    self.canvas.itemconfig(self.selected_item, outline=self.current_color, fill=fill_col, width=w)
            self.update_handles()

    def choose_color(self):
        color_code = colorchooser.askcolor(title="Renk Seç", color=self.current_color)[1]
        if color_code:
            self.current_color = color_code
            self.color_btn.config(bg=self.current_color, fg=self.current_color, activebackground=self.current_color)
            self.apply_properties_to_selected()

    def scale_selected(self, factor):
        if not self.selected_item: return
        self.save_state()
        
        if isinstance(self.selected_item, str) and self.selected_item.startswith("3d_"):
            obj = next((o for o in self.objects_3d if o["id"] == self.selected_item), None)
            if obj:
                obj["size"] = max(2, obj["size"] * factor)
                self.render_3d_objects()
        else:
            coords = self.canvas.coords(self.selected_item)
            if coords:
                cx = sum(coords[0::2]) / (len(coords)//2)
                cy = sum(coords[1::2]) / (len(coords)//2)
                new_coords = []
                for i in range(0, len(coords), 2):
                    nx = cx + (coords[i] - cx) * factor
                    ny = cy + (coords[i+1] - cy) * factor
                    new_coords.extend([nx, ny])
                self.canvas.coords(self.selected_item, *new_coords)
        self.update_handles()

    def update_handles(self):
        self.canvas.delete("handle")
        if not self.selected_item: return
        
        bbox = self.canvas.bbox(self.selected_item)
        if not bbox: return
        x1, y1, x2, y2 = bbox
        
        pad = 5
        selection_color = "#8e44ad"
        
        self.canvas.create_rectangle(
            x1 - pad, y1 - pad, x2 + pad, y2 + pad,
            outline=selection_color, dash=(6, 4), width=1, tags=("handle", "box")
        )
        
        handle_size = 4
        def draw_handle(x, y, handle_name):
            self.canvas.create_rectangle(
                x - handle_size, y - handle_size, x + handle_size, y + handle_size,
                fill=selection_color, outline="white", width=1, tags=("handle", handle_name)
            )

        if isinstance(self.selected_item, str) and self.selected_item.startswith("3d_"):
            draw_handle(x1 - pad, y1 - pad, "nw")
            draw_handle(x2 + pad, y1 - pad, "ne")
            draw_handle(x1 - pad, y2 + pad, "sw")
            draw_handle(x2 + pad, y2 + pad, "se")
        else:
            item_type = self.canvas.type(self.selected_item)
            if item_type == "line":
                coords = self.canvas.coords(self.selected_item)
                draw_handle(coords[0], coords[1], "start")
                draw_handle(coords[2], coords[3], "end")
            else:
                draw_handle(x1 - pad, y1 - pad, "nw")
                draw_handle(x2 + pad, y1 - pad, "ne")
                draw_handle(x1 - pad, y2 + pad, "sw")
                draw_handle(x2 + pad, y2 + pad, "se")

    def render_3d_objects(self):
        self.canvas.delete("3d_obj")
        global_faces_to_draw = [] 
        
        for obj in self.objects_3d:
            cx, cy, size = obj["cx"], obj["cy"], obj["size"]
            rx, ry, rz = obj.get("rot_x", 0), obj.get("rot_y", 0), obj.get("rot_z", 0)
            
            rotated_verts = []
            for v in obj["vertices"]:
                x1 = v[0] * math.cos(ry) - v[2] * math.sin(ry)
                y1 = v[1]
                z1 = v[0] * math.sin(ry) + v[2] * math.cos(ry)

                x2 = x1
                y2 = y1 * math.cos(rx) - z1 * math.sin(rx)
                z2 = y1 * math.sin(rx) + z1 * math.cos(rx)

                x3 = x2 * math.cos(rz) - y2 * math.sin(rz)
                y3 = x2 * math.sin(rz) + y2 * math.cos(rz)
                z3 = z2

                gx1 = x3 * math.cos(self.cam_rot_y) - z3 * math.sin(self.cam_rot_y)
                gy1 = y3
                gz1 = x3 * math.sin(self.cam_rot_y) + z3 * math.cos(self.cam_rot_y)

                gx2 = gx1
                gy2 = gy1 * math.cos(self.cam_rot_x) - gz1 * math.sin(self.cam_rot_x)
                gz2 = gy1 * math.sin(self.cam_rot_x) + gz1 * math.cos(self.cam_rot_x)

                rotated_verts.append([gx2, gy2, gz2])

            for face in obj["faces"]:
                pts = [rotated_verts[i] for i in face]
                v1 = [pts[1][0]-pts[0][0], pts[1][1]-pts[0][1], pts[1][2]-pts[0][2]]
                v2 = [pts[2][0]-pts[0][0], pts[2][1]-pts[0][1], pts[2][2]-pts[0][2]]
                
                # math_3d kullanımları
                normal = math_3d.normalize(math_3d.cross_product(v1, v2))
                
                if normal[2] > 0:
                    intensity = math_3d.dot_product(normal, self.light_dir)
                    color = math_3d.shade_color(obj["color"], abs(intensity) + 0.2)
                    
                    coords2d = []
                    avg_z = sum(p[2] for p in pts) / len(pts)
                    
                    for p in pts:
                        coords2d.extend([cx + p[0]*size, cy + p[1]*size]) 
                    
                    global_faces_to_draw.append((avg_z, coords2d, color, obj))

        global_faces_to_draw.sort(key=lambda x: x[0], reverse=False)

        for face_data in global_faces_to_draw:
            avg_z, coords2d, color, obj = face_data
            mode = obj.get("style", "fill")
            width = obj.get("width", 2)

            if mode == "fill":
                self.canvas.create_polygon(*coords2d, fill=color, outline="black", width=width, tags=("3d_obj", obj["id"]))
            else:
                self.canvas.create_polygon(*coords2d, fill="", outline=obj["color"], width=width, tags=("3d_obj", obj["id"]))

    def create_3d_object(self, obj_type, x, y, size):
        self.save_state()
        self.id_counter += 1
        obj_id = f"3d_{len(self.objects_3d)}_{self.id_counter}"
        
        iso_ry = math.pi / 4 
        iso_rx = -math.asin(1 / math.sqrt(3))

        obj = {
            "id": obj_id, "type": obj_type, "cx": x, "cy": y, "size": size,
            "rot_x": iso_rx, "rot_y": iso_ry, "rot_z": 0.0, "color": self.current_color,
            "style": self.style_mode.get(), "width": self.line_width.get()
        }
        
        if obj_type == "cube":
            obj["vertices"] = [[-1,-1,-1], [1,-1,-1], [1,1,-1], [-1,1,-1], [-1,-1,1], [1,-1,1], [1,1,1], [-1,1,1]]
            obj["faces"] = [(0,3,2,1), (1,2,6,5), (5,6,7,4), (4,7,3,0), (4,0,1,5), (3,7,6,2)]
        elif obj_type == "pyramid":
            obj["vertices"] = [[0,-1,0], [-1,1,-1], [1,1,-1], [1,1,1], [-1,1,1]]
            obj["faces"] = [(0,1,2), (0,2,3), (0,3,4), (0,4,1), (1,4,3,2)]
            
        self.objects_3d.append(obj)
        self.selected_item = obj_id
        self.render_3d_objects()
        self.update_handles()

    def get_current_state(self):
        data_2d = []
        for item in self.canvas.find_all():
            tags = self.canvas.gettags(item)
            if "grid_line" in tags or "3d_obj" in tags or "handle" in tags: continue 
            
            item_type = self.canvas.type(item)
            data_2d.append({
                "type": item_type,
                "coords": self.canvas.coords(item),
                "fill": self.canvas.itemcget(item, "fill"),
                "outline": self.canvas.itemcget(item, "outline") if item_type != "line" else "",
                "width": self.canvas.itemcget(item, "width")
            })
        return {"2d": data_2d, "3d": copy.deepcopy(self.objects_3d)}

    def render_state(self, state_data):
        self.canvas.delete("all")
        self.draw_grid_lines()
        
        for item_data in state_data.get("2d", []):
            coords, fill_color, outline_color, width = item_data["coords"], item_data["fill"], item_data["outline"], item_data["width"]
            
            if item_data["type"] == "line": self.canvas.create_line(*coords, fill=fill_color, width=width)
            elif item_data["type"] == "oval": self.canvas.create_oval(*coords, outline=outline_color, fill=fill_color, width=width)
            elif item_data["type"] == "polygon": self.canvas.create_polygon(*coords, outline=outline_color, fill=fill_color, width=width)
            
        self.objects_3d = copy.deepcopy(state_data.get("3d", []))
        
        max_id = 0
        for obj in self.objects_3d:
            try:
                parts = obj["id"].split("_")
                if len(parts) >= 3:
                    obj_id_num = int(parts[2])
                    if obj_id_num > max_id: max_id = obj_id_num
            except Exception:
                pass
        self.id_counter = max_id
        
        self.render_3d_objects()
        self.selected_item = None
        self.update_handles()

    def save_state(self):
        self.history.append(self.get_current_state())
        self.redo_history.clear()
        if len(self.history) > 30: self.history.pop(0)

    def undo(self, event=None):
        if self.history:
            self.redo_history.append(self.get_current_state())
            self.render_state(self.history.pop())

    def redo(self, event=None):
        if self.redo_history:
            self.history.append(self.get_current_state())
            self.render_state(self.redo_history.pop())

    def save_file(self):
        filepath = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Dosyaları", "*.json")])
        if filepath:
            with open(filepath, "w") as file: json.dump(self.get_current_state(), file)

    def load_file(self):
        filepath = filedialog.askopenfilename(filetypes=[("JSON Dosyaları", "*.json")])
        if filepath:
            self.save_state()
            try:
                with open(filepath, "r") as file: 
                    self.render_state(json.load(file))
            except (json.JSONDecodeError, FileNotFoundError, Exception) as e:
                messagebox.showerror("Yükleme Hatası", f"Dosya yüklenemedi. Formatı bozuk veya hatalı olabilir.\nDetay: {e}")

    def draw_grid_lines(self):
        self.canvas.delete("grid_line")
        if self.show_grid.get():
            w, h = 3000, 3000
            for i in range(0, w, self.grid_size):
                self.canvas.create_line(i, 0, i, h, fill="#ecf0f1", tags="grid_line")
                self.canvas.create_line(0, i, w, i, fill="#ecf0f1", tags="grid_line")
            self.canvas.tag_lower("grid_line")

    def get_snapped_coord(self, val):
        return round(val / self.grid_size) * self.grid_size if self.snap_grid.get() else val

    def bring_front(self):
        if not self.selected_item: return
        self.save_state()
        if isinstance(self.selected_item, str) and self.selected_item.startswith("3d_"):
            obj = next((o for o in self.objects_3d if o["id"] == self.selected_item), None)
            if obj:
                self.objects_3d.remove(obj)
                self.objects_3d.append(obj)
                self.render_3d_objects()
        
        self.canvas.tag_raise(self.selected_item)
        self.update_handles()
            
    def send_back(self):
        if not self.selected_item: return
        self.save_state()
        if isinstance(self.selected_item, str) and self.selected_item.startswith("3d_"):
            obj = next((o for o in self.objects_3d if o["id"] == self.selected_item), None)
            if obj:
                self.objects_3d.remove(obj)
                self.objects_3d.insert(0, obj)
                self.render_3d_objects()
                
        self.canvas.tag_lower(self.selected_item)
        self.canvas.tag_lower("grid_line")
        self.update_handles()
            
    def delete_item(self):
        if self.selected_item:
            self.save_state()
            if isinstance(self.selected_item, str) and self.selected_item.startswith("3d_"):
                self.objects_3d = [o for o in self.objects_3d if o["id"] != self.selected_item]
                self.render_3d_objects()
            else: 
                self.canvas.delete(self.selected_item)
            self.selected_item = None
            self.update_handles()

    def duplicate_item(self):
        if self.selected_item:
            self.save_state()
            if isinstance(self.selected_item, str) and self.selected_item.startswith("3d_"):
                obj = next((o for o in self.objects_3d if o["id"] == self.selected_item), None)
                if obj:
                    new_obj = copy.deepcopy(obj)
                    self.id_counter += 1
                    new_obj["id"] = f"3d_{len(self.objects_3d)}_{self.id_counter}"
                    new_obj["cx"] += self.grid_size * 2
                    new_obj["cy"] += self.grid_size * 2
                    self.objects_3d.append(new_obj)
                    self.selected_item = new_obj["id"]
                    self.render_3d_objects()
            else:
                item_type = self.canvas.type(self.selected_item)
                new_coords = [c + (self.grid_size * 2) for c in self.canvas.coords(self.selected_item)]
                fill_color, width = self.canvas.itemcget(self.selected_item, "fill"), self.canvas.itemcget(self.selected_item, "width")
                
                if item_type == "line": self.selected_item = self.canvas.create_line(*new_coords, fill=fill_color, width=width)
                else:
                    outline_color = self.canvas.itemcget(self.selected_item, "outline")
                    if item_type == "oval": self.selected_item = self.canvas.create_oval(*new_coords, outline=outline_color, fill=fill_color, width=width)
                    elif item_type == "polygon": self.selected_item = self.canvas.create_polygon(*new_coords, outline=outline_color, fill=fill_color, width=width)
            self.update_handles()

    def rotate_selected(self, angle_degrees, axis="y"):
        if not self.selected_item: return
        is_3d = isinstance(self.selected_item, str) and self.selected_item.startswith("3d_")
        
        if axis in ["x", "y"]: 
            if not is_3d: return
            self.save_state()
            obj = next((o for o in self.objects_3d if o["id"] == self.selected_item), None)
            if obj:
                rad = math.radians(angle_degrees)
                if axis == "y": obj["rot_y"] += rad
                elif axis == "x": obj["rot_x"] += rad
                self.render_3d_objects()
                
        elif axis == "z":
            self.save_state()
            if is_3d:
                obj = next((o for o in self.objects_3d if o["id"] == self.selected_item), None)
                if obj:
                    rad = math.radians(angle_degrees)
                    obj["rot_z"] = obj.get("rot_z", 0) + rad
                    self.render_3d_objects()
            else:
                item_type = self.canvas.type(self.selected_item)
                if item_type in ["polygon", "line"]:
                    coords = self.canvas.coords(self.selected_item)
                    if coords:
                        cx = sum(coords[0::2]) / (len(coords)//2)
                        cy = sum(coords[1::2]) / (len(coords)//2)
                        rad = math.radians(angle_degrees)
                        new_coords = []
                        for i in range(0, len(coords), 2):
                            x, y = coords[i], coords[i+1]
                            nx = cx + (x - cx) * math.cos(rad) - (y - cy) * math.sin(rad)
                            ny = cy + (x - cx) * math.sin(rad) + (y - cy) * math.cos(rad)
                            new_coords.extend([nx, ny])
                        self.canvas.coords(self.selected_item, *new_coords)
                elif item_type == "oval": pass
                    
        self.update_handles()

    def select_tool(self, tool_name):
        self.current_tool = tool_name
        self.canvas.config(cursor="hand2" if tool_name == "select" else "cross")
        if self.temp_item:
            self.canvas.delete(self.temp_item)
            self.temp_item = None

    def draw_shape(self, x1, y1, x2, y2):
        mode = self.style_mode.get()
        fill_color = self.current_color if mode == "fill" else ""
        width = self.line_width.get()
        
        if self.current_tool == "line": 
            return self.canvas.create_line(x1, y1, x2, y2, fill=self.current_color, width=width)
        elif self.current_tool == "rectangle": 
            return self.canvas.create_polygon(x1, y1, x2, y1, x2, y2, x1, y2, outline=self.current_color, fill=fill_color, width=width)
        elif self.current_tool == "triangle": 
            return self.canvas.create_polygon(x1 + (x2 - x1) / 2, y1, x2, y2, x1, y2, outline=self.current_color, fill=fill_color, width=width)
        elif self.current_tool == "circle": 
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            rx, ry = abs(x2 - x1) / 2, abs(y2 - y1) / 2
            points = []
            for i in range(36):
                ang = math.radians(i * 10)
                points.extend([cx + rx * math.cos(ang), cy + ry * math.sin(ang)])
            return self.canvas.create_polygon(*points, outline=self.current_color, fill=fill_color, width=width)

    def clear_canvas(self):
        self.save_state()
        self.canvas.delete("all")
        self.objects_3d.clear()
        self.selected_item = None
        self.draw_grid_lines()

    def on_mouse_press(self, event):
        self.start_x = self.get_snapped_coord(event.x)
        self.start_y = self.get_snapped_coord(event.y)

        items = self.canvas.find_overlapping(self.start_x - 6, self.start_y - 6, self.start_x + 6, self.start_y + 6)
        
        target_item = None
        target_tags = []
        
        for i in reversed(items):
            t = self.canvas.gettags(i)
            if "grid_line" in t or ("handle" in t and "box" in t): continue
            target_item = i
            target_tags = t
            break

        if self.current_tool == "select" and "handle" in target_tags:
            self.dragging_handle = target_tags[1]
            self.save_state()
            
            if isinstance(self.selected_item, str):
                obj = next((o for o in self.objects_3d if o["id"] == self.selected_item), None)
                self.init_coords = obj["size"] if obj else 50
            else:
                self.init_coords = self.canvas.coords(self.selected_item)
            return

        if self.current_tool == "select":
            self.dragging_handle = None
            if target_item:
                self._pending_select_save = True
                self._drag_moved = False
                obj_id = next((tag for tag in target_tags if tag.startswith("3d_") and tag != "3d_obj"), None)
                if obj_id: self.selected_item = obj_id
                else: self.selected_item = target_item
                
                if obj_id: self.render_3d_objects()
                self.update_handles()
            else:
                self.selected_item = None
                self.update_handles()
                
        elif self.current_tool in ["cube", "pyramid"]:
            self.is_creating_3d = True
            self.create_3d_object(self.current_tool, self.start_x, self.start_y, 1)

    def on_mouse_drag(self, event):
        current_x = self.get_snapped_coord(event.x)
        current_y = self.get_snapped_coord(event.y)

        if self.dragging_handle:
            if isinstance(self.selected_item, str) and self.selected_item.startswith("3d_"):
                obj = next((o for o in self.objects_3d if o["id"] == self.selected_item), None)
                if obj:
                    dist = math.hypot(current_x - obj["cx"], current_y - obj["cy"])
                    obj["size"] = max(5, dist / 1.2)
                    self.render_3d_objects()
            else:
                item_type = self.canvas.type(self.selected_item)
                if item_type == "line":
                    coords = list(self.init_coords)
                    if self.dragging_handle == "start": coords[0], coords[1] = current_x, current_y
                    elif self.dragging_handle == "end": coords[2], coords[3] = current_x, current_y
                    self.canvas.coords(self.selected_item, *coords)
                elif item_type == "oval":
                    x1, y1, x2, y2 = self.init_coords
                    if self.dragging_handle == "nw": x1, y1 = current_x, current_y
                    elif self.dragging_handle == "ne": x2, y1 = current_x, current_y
                    elif self.dragging_handle == "sw": x1, y2 = current_x, current_y
                    elif self.dragging_handle == "se": x2, y2 = current_x, current_y
                    self.canvas.coords(self.selected_item, x1, y1, x2, y2)
                elif item_type == "polygon":
                    coords = list(self.init_coords)
                    min_x, max_x = min(coords[0::2]), max(coords[0::2])
                    min_y, max_y = min(coords[1::2]), max(coords[1::2])
                    
                    if min_x == max_x: max_x += 0.001
                    if min_y == max_y: max_y += 0.001
                    
                    rx, ry, sx, sy = min_x, min_y, 1.0, 1.0
                    if self.dragging_handle == "nw":
                        rx, ry = max_x, max_y
                        sx, sy = (max_x - current_x) / (max_x - min_x), (max_y - current_y) / (max_y - min_y)
                    elif self.dragging_handle == "ne":
                        rx, ry = min_x, max_y
                        sx, sy = (current_x - min_x) / (max_x - min_x), (max_y - current_y) / (max_y - min_y)
                    elif self.dragging_handle == "sw":
                        rx, ry = max_x, min_y
                        sx, sy = (max_x - current_x) / (max_x - min_x), (current_y - min_y) / (max_y - min_y)
                    elif self.dragging_handle == "se":
                        rx, ry = min_x, min_y
                        sx, sy = (current_x - min_x) / (max_x - min_x), (current_y - min_y) / (max_y - min_y)
                    
                    new_coords = []
                    for i in range(0, len(coords), 2):
                        nx = rx + (coords[i] - rx) * sx
                        ny = ry + (coords[i+1] - ry) * sy
                        new_coords.extend([nx, ny])
                    self.canvas.coords(self.selected_item, *new_coords)
            
            self.update_handles()
            return

        if getattr(self, 'is_creating_3d', False) and isinstance(self.selected_item, str):
            obj = next((o for o in self.objects_3d if o["id"] == self.selected_item), None)
            if obj:
                size = math.hypot(current_x - self.start_x, current_y - self.start_y)
                obj["size"] = max(1, size)
                self.render_3d_objects()
            return

        if self.current_tool == "select" and self.selected_item:
            dx, dy = current_x - self.start_x, current_y - self.start_y
            if dx != 0 or dy != 0:
                if getattr(self, '_pending_select_save', False) and not getattr(self, '_drag_moved', False):
                    self.save_state()
                    self._drag_moved = True
                    self._pending_select_save = False
                if isinstance(self.selected_item, str) and self.selected_item.startswith("3d_"):
                    obj = next((o for o in self.objects_3d if o["id"] == self.selected_item), None)
                    if obj:
                        obj["cx"] += dx; obj["cy"] += dy
                        self.render_3d_objects()
                else: 
                    self.canvas.move(self.selected_item, dx, dy)
                
                self.start_x, self.start_y = current_x, current_y
                self.update_handles()
            
        elif self.current_tool in ["line", "rectangle", "circle", "triangle"]:
            if self.temp_item: self.canvas.delete(self.temp_item)
            self.temp_item = self.draw_shape(self.start_x, self.start_y, current_x, current_y)

    def on_mouse_release(self, event):
        if self.dragging_handle:
            self.dragging_handle = None
            return

        if getattr(self, 'is_creating_3d', False):
            self.is_creating_3d = False
            obj = next((o for o in self.objects_3d if o["id"] == self.selected_item), None)
            if obj and obj["size"] < 5: self.objects_3d.remove(obj)
            self.selected_item = None
            self.render_3d_objects()
            self.update_handles()
            return

        if self.current_tool == "select": return
        
        current_x = self.get_snapped_coord(event.x)
        current_y = self.get_snapped_coord(event.y)
        
        if abs(current_x - self.start_x) < 2 and abs(current_y - self.start_y) < 2:
            if self.temp_item:
                self.canvas.delete(self.temp_item)
                self.temp_item = None
            return
        
        if self.temp_item:
            self.canvas.delete(self.temp_item)
            self.temp_item = None
            
        if self.current_tool in ["line", "rectangle", "circle", "triangle"]:
            self.save_state()
            self.draw_shape(self.start_x, self.start_y, current_x, current_y)
            self.selected_item = None
            self.update_handles()

    def on_right_press(self, event):
        self.is_rotating = True
        self.right_start_x = event.x
        self.right_start_y = event.y

    def on_right_drag(self, event):
        if getattr(self, 'is_rotating', False):
            dx = event.x - self.right_start_x
            dy = event.y - self.right_start_y
            
            self.cam_rot_y += dx * 0.01
            self.cam_rot_x -= dy * 0.01
            
            self.right_start_x = event.x
            self.right_start_y = event.y
            self.render_3d_objects()
            self.update_handles()
            
    def on_right_release(self, event):
        self.is_rotating = False
        self.render_3d_objects()
        self.update_handles()

if __name__ == "__main__":
    root = tk.Tk()
    app = MiniCADApp(root)
    root.mainloop()