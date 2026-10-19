import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageDraw
import math

def draw_pid_connections(equipment_data, connection_data, overlap_padding=10):
    def get_equipment_center(eq):
        return (eq['x'] + eq['width']/2, eq['y'] + eq['height']/2)
    
    def are_aligned(eq1, eq2, tolerance=5):
        c1 = get_equipment_center(eq1)
        c2 = get_equipment_center(eq2)
        return abs(c1[0] - c2[0]) <= tolerance or abs(c1[1] - c2[1]) <= tolerance
    
    def get_connection_points(eq1, eq2):
        c1 = get_equipment_center(eq1)
        c2 = get_equipment_center(eq2)
        
        if c1[0] < c2[0]:
            x1 = eq1['x'] + eq1['width']
            x2 = eq2['x']
        else:
            x1 = eq1['x']
            x2 = eq2['x'] + eq2['width']
        
        y1 = eq1['y'] + eq1['height'] / 2
        y2 = eq2['y'] + eq2['height'] / 2
        
        return (x1, y1), (x2, y2)
    
    def check_overlap(path, equipment):
        for i in range(len(path) - 1):
            x1, y1 = path[i]
            x2, y2 = path[i+1]
            if x1 == x2:  # Vertical line
                if (equipment['x'] - overlap_padding < x1 < equipment['x'] + equipment['width'] + overlap_padding and
                    min(y1, y2) < equipment['y'] + equipment['height'] and max(y1, y2) > equipment['y']):
                    return True
            else:  # Horizontal line
                if (equipment['y'] - overlap_padding < y1 < equipment['y'] + equipment['height'] + overlap_padding and
                    min(x1, x2) < equipment['x'] + equipment['width'] and max(x1, x2) > equipment['x']):
                    return True
        return False
    
    def route_orthogonal_connection(start, end, branch_point=None):
        x1, y1 = start
        x2, y2 = end
        
        if branch_point:
            bx, by = branch_point
            return [
                (x1, y1),
                (bx, y1),
                (bx, y2),
                (x2, y2)
            ]
        else:
            mid_x = (x1 + x2) / 2
            return [
                (x1, y1),
                (mid_x, y1),
                (mid_x, y2),
                (x2, y2)
            ]
    
    def adjust_path(path, from_eq, to_eq, all_equipment):
        original_path = path.copy()
        shift_amounts = [overlap_padding, -overlap_padding]
        
        for shift in shift_amounts:
            # Adjust path closer to 'from' equipment
            new_path = path.copy()
            new_path[1] = (from_eq['x'] + from_eq['width'] + shift if shift > 0 else from_eq['x'] + shift, new_path[1][1])
            new_path[2] = (new_path[1][0], new_path[2][1])
            
            if all(not check_overlap(new_path, eq) for eq in all_equipment if eq != from_eq and eq != to_eq):
                return new_path, 'blue'
            
            # Adjust path closer to 'to' equipment
            new_path = path.copy()
            new_path[2] = (to_eq['x'] - shift if shift > 0 else to_eq['x'] + to_eq['width'] + shift, new_path[2][1])
            new_path[1] = (new_path[2][0], new_path[1][1])
            
            if all(not check_overlap(new_path, eq) for eq in all_equipment if eq != from_eq and eq != to_eq):
                return new_path, 'blue'
        
        # If we couldn't avoid overlap, return the original path colored red
        return original_path, 'red'
    
    connections_to_draw = []
    branched_connections = {}
    
    for from_id, to_id, conn_type in connection_data:
        from_eq = next(eq for eq in equipment_data if eq['id'] == from_id)
        to_eq = next(eq for eq in equipment_data if eq['id'] == to_id)
        
        if to_id not in branched_connections:
            branched_connections[to_id] = []
        
        branched_connections[to_id].append(from_eq)
    
    for from_id, to_id, conn_type in connection_data:
        from_eq = next(eq for eq in equipment_data if eq['id'] == from_id)
        to_eq = next(eq for eq in equipment_data if eq['id'] == to_id)
        
        start_point, end_point = get_connection_points(from_eq, to_eq)
        
        if len(branched_connections[to_id]) > 1 and any(are_aligned(eq, from_eq) for eq in branched_connections[to_id] if eq['id'] != from_id):
            aligned_eq = [eq for eq in branched_connections[to_id] if are_aligned(eq, from_eq) and eq['id'] != from_id][0]
            _, aligned_end = get_connection_points(aligned_eq, to_eq)
            branch_point = ((start_point[0] + aligned_end[0]) / 2, start_point[1])
            path = route_orthogonal_connection(start_point, end_point, branch_point)
        else:
            path = route_orthogonal_connection(start_point, end_point)
        
        adjusted_path, color = adjust_path(path, from_eq, to_eq, equipment_data)
        
        connections_to_draw.append({
            'path': adjusted_path,
            'type': conn_type,
            'color': color
        })
    
    return connections_to_draw

class PIDEditor(tk.Tk):
    def __init__(self, equipment_data, connection_data):
        super().__init__()
        self.title("P&ID Editor")
        self.geometry("1000x800")

        self.equipment_data = equipment_data
        self.connection_data = connection_data
        self.connections = draw_pid_connections(equipment_data, connection_data)
        
        self.canvas = tk.Canvas(self, width=800, height=600, bg='white')
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.sidebar = ttk.Frame(self, padding="3 3 12 12")
        self.sidebar.pack(side=tk.RIGHT, fill=tk.Y)

        self.selected_item = None
        self.drag_data = {"x": 0, "y": 0, "item": None, "segment": None}

        self.grid_size = 20
        self.snap_threshold = 15

        self.draw_diagram()
        self.create_sidebar()

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

    def draw_diagram(self):
        self.canvas.delete("all")
        self.scale = min(800 / max(eq['x'] + eq['width'] for eq in self.equipment_data),
                         600 / max(eq['y'] + eq['height'] for eq in self.equipment_data))

        for x in range(0, 800, self.grid_size):
            self.canvas.create_line(x, 0, x, 600, fill='lightgray')
        for y in range(0, 600, self.grid_size):
            self.canvas.create_line(0, y, 800, y, fill='lightgray')

        for eq in self.equipment_data:
            x, y = eq['x'] * self.scale, eq['y'] * self.scale
            w, h = eq['width'] * self.scale, eq['height'] * self.scale
            eq['canvas_item'] = self.canvas.create_rectangle(x, y, x+w, y+h, fill='lightgray', tags=('equipment', eq['id']))
            self.canvas.create_text(x+w/2, y+h/2, text=eq['id'], tags=('equipment', eq['id']))

        for conn in self.connections:
            path = conn['path']
            color = conn['color']
            line_items = []
            for i in range(len(path) - 1):
                start = path[i][0] * self.scale, path[i][1] * self.scale
                end = path[i+1][0] * self.scale, path[i+1][1] * self.scale
                line = self.canvas.create_line(start[0], start[1], end[0], end[1], fill=color, width=2, tags=('connection',))
                line_items.append(line)
            conn['canvas_items'] = line_items

    def create_sidebar(self):
        ttk.Label(self.sidebar, text="Selected Item:").pack()
        self.selected_label = ttk.Label(self.sidebar, text="None")
        self.selected_label.pack()

        ttk.Button(self.sidebar, text="Redraw Connections", command=self.redraw_connections).pack(pady=10)

        self.mode_var = tk.StringVar(value="equipment")
        ttk.Radiobutton(self.sidebar, text="Move Equipment", variable=self.mode_var, value="equipment").pack()
        ttk.Radiobutton(self.sidebar, text="Adjust Paths", variable=self.mode_var, value="path").pack()

    def on_press(self, event):
        item = self.canvas.find_closest(event.x, event.y)[0]
        tags = self.canvas.gettags(item)

        

        
        if 'equipment' in tags:
            self.mode_var.set('equipment')
            self.selected_item = next(eq for eq in self.equipment_data if eq['id'] in tags)
            self.selected_label.config(text=f"Equipment: {self.selected_item['id']}")
        elif 'connection' in tags:
            self.mode_var.set('path')
            connection = next(conn for conn in self.connections if item in conn['canvas_items'])
            self.selected_item = connection
            segment_index = connection['canvas_items'].index(item)
            self.selected_label.config(text=f"Connection: {self.connection_data[self.connections.index(connection)]}")
            self.drag_data["segment"] = segment_index
        else:
            self.selected_item = None
            self.selected_label.config(text="None")

        self.drag_data["item"] = item
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y
        self.redraw_connections()


    def on_drag(self, event):
        mode = self.mode_var.get()
        if mode == "equipment" and self.selected_item and 'canvas_item' in self.selected_item:
            dx = event.x - self.drag_data["x"]
            dy = event.y - self.drag_data["y"]
            self.canvas.move(self.drag_data["item"], dx, dy)
            self.drag_data["x"] = event.x
            self.drag_data["y"] = event.y
            
            self.selected_item['x'] += dx / self.scale
            self.selected_item['y'] += dy / self.scale
            self.check_object_overlaps()
        elif mode == "path" and self.selected_item and 'canvas_items' in self.selected_item:
            segment = self.drag_data["segment"]
            if segment is not None and 0 < segment < len(self.selected_item['path']) - 1:
                start = self.selected_item['path'][segment - 1]
                end = self.selected_item['path'][segment + 1]
                
                if start[0] == end[0]:  # Vertical segment
                    dy = (event.y - self.drag_data["y"]) / self.scale
                    self.selected_item['path'][segment] = (
                        self.selected_item['path'][segment][0],
                        self.selected_item['path'][segment][1] + dy
                    )
                    self.drag_data["y"] = event.y
                else:  # Horizontal segment
                    dx = (event.x - self.drag_data["x"]) / self.scale
                    self.selected_item['path'][segment] = (
                        self.selected_item['path'][segment][0] + dx,
                        self.selected_item['path'][segment][1]
                    )
                    self.drag_data["x"] = event.x
                
                self.redraw_connection(self.selected_item)
                self.check_path_overlaps()
                self.adjust_adjacent_segments()
        self.redraw_connections()


    def on_release(self, event):
        mode = self.mode_var.get()
        if mode == "equipment" and self.selected_item and 'canvas_item' in self.selected_item:
            self.snap_to_grid_and_equipment()
        elif mode == "path":
            self.check_path_overlaps()
            self.adjust_adjacent_segments()
        self.drag_data["item"] = None
        self.drag_data["x"] = 0
        self.drag_data["y"] = 0
        self.drag_data["segment"] = None
        self.redraw_connections()


    def adjust_adjacent_segments(self):
        if self.selected_item and 'canvas_items' in self.selected_item:
            segment = self.drag_data["segment"]
            if segment is not None and 0 < segment < len(self.selected_item['path']) - 1:
                path = self.selected_item['path']
                prev_point = path[segment - 1]
                curr_point = path[segment]
                next_point = path[segment + 1]

                if prev_point[0] == curr_point[0]:  # Vertical segment was moved
                    path[segment - 1] = (curr_point[0], prev_point[1])
                    path[segment + 1] = (next_point[0], curr_point[1])
                else:  # Horizontal segment was moved
                    path[segment - 1] = (prev_point[0], curr_point[1])
                    path[segment + 1] = (curr_point[0], next_point[1])

                self.redraw_connection(self.selected_item)

    def snap_to_grid_and_equipment(self):
        x, y = self.selected_item['x'], self.selected_item['y']
        w, h = self.selected_item['width'], self.selected_item['height']

        # Snap to grid
        grid_x = round(x / self.grid_size) * self.grid_size
        grid_y = round(y / self.grid_size) * self.grid_size

        # Snap to nearby equipment
        for eq in self.equipment_data:
            if eq != self.selected_item:
                # Snap left edge to right edge of other equipment
                if abs(x - (eq['x'] + eq['width'])) < self.snap_threshold:
                    grid_x = eq['x'] + eq['width']
                # Snap right edge to left edge of other equipment
                elif abs((x + w) - eq['x']) < self.snap_threshold:
                    grid_x = eq['x'] - w
                # Snap top edge to bottom edge of other equipment
                if abs(y - (eq['y'] + eq['height'])) < self.snap_threshold:
                    grid_y = eq['y'] + eq['height']
                # Snap bottom edge to top edge of other equipment
                elif abs((y + h) - eq['y']) < self.snap_threshold:
                    grid_y = eq['y'] - h

        # Update position
        dx = (grid_x - x) * self.scale
        dy = (grid_y - y) * self.scale
        self.canvas.move(self.selected_item['canvas_item'], dx, dy)
        self.selected_item['x'] = grid_x
        self.selected_item['y'] = grid_y

    def check_path_overlaps(self):
        if self.selected_item and 'canvas_items' in self.selected_item:
            path = self.selected_item['path']
            for eq in self.equipment_data:
                if self.path_overlaps_equipment(path, eq):
                    self.selected_item['color'] = 'red'
                    break
            else:
                self.selected_item['color'] = 'blue'
            self.redraw_connection(self.selected_item)

    def check_object_overlaps(self):
        if self.selected_item and 'canvas_item' in self.selected_item:
            x, y = self.selected_item['x'], self.selected_item['y']
            w, h = self.selected_item['width'], self.selected_item['height']
            for eq in self.equipment_data:
                if eq != self.selected_item and self.rectangles_overlap(x, y, w, h, eq['x'], eq['y'], eq['width'], eq['height']):
                    self.selected_item['color'] = 'red'
                    break
            else:
                self.selected_item['color'] = 'blue'
            self.redraw_equipment(self.selected_item)

    def rectangles_overlap(self, x1, y1, w1, h1, x2, y2, w2, h2):
        return (x1 < x2 + w2 and x1 + w1 > x2 and y1 < y2 + h2 and y1 + h1 > y2)

    def redraw_equipment(self, equipment):
        self.canvas.delete(equipment['canvas_item'])
        x, y = equipment['x'] * self.scale, equipment['y'] * self.scale
        w, h = equipment['width'] * self.scale, equipment['height'] * self.scale
        equipment['canvas_item'] = self.canvas.create_rectangle(x, y, x+w, y+h, fill=equipment['color'], tags=('equipment', equipment['id']))
        self.canvas.create_text(x+w/2, y+h/2, text=equipment['id'], tags=('equipment', equipment['id']))

    def path_overlaps_equipment(self, path, equipment):
        for i in range(len(path) - 1):
            x1, y1 = path[i]
            x2, y2 = path[i+1]
            if x1 == x2:  # Vertical line
                if (equipment['x'] < x1 < equipment['x'] + equipment['width'] and
                    min(y1, y2) < equipment['y'] + equipment['height'] and
                    max(y1, y2) > equipment['y']):
                    return True
            else:  # Horizontal line
                if (equipment['y'] < y1 < equipment['y'] + equipment['height'] and
                    min(x1, x2) < equipment['x'] + equipment['width'] and
                    max(x1, x2) > equipment['x']):
                    return True
        return False

    def redraw_connection(self, connection):
        for item in connection['canvas_items']:
            self.canvas.delete(item)
        line_items = []
        path = connection['path']
        color = connection['color']
        for i in range(len(path) - 1):
            start = path[i][0] * self.scale, path[i][1] * self.scale
            end = path[i+1][0] * self.scale, path[i+1][1] * self.scale
            line = self.canvas.create_line(start[0], start[1], end[0], end[1], fill=color, width=2, tags=('connection',))
            line_items.append(line)
        connection['canvas_items'] = line_items

    def redraw_connections(self):
        mode = self.mode_var.get()

        if mode == "path":
            return
        
        self.connections = draw_pid_connections(self.equipment_data, self.connection_data)
        self.draw_diagram()

# Example usage
equipment_data = [
    {'id': 'T-100', 'x': 100, 'y': 50, 'width': 50, 'height': 100},
    {'id': 'T-101', 'x': 100, 'y': 200, 'width': 50, 'height': 100},
    {'id': 'P-102', 'x': 200, 'y': 50, 'width': 30, 'height': 30},
    {'id': 'P-103', 'x': 200, 'y': 100, 'width': 30, 'height': 30},
    {'id': 'V-104', 'x': 300, 'y': 150, 'width': 40, 'height': 40},
    {'id': 'E-105', 'x': 400, 'y': 50, 'width': 60, 'height': 30},
    {'id': 'E-106', 'x': 500, 'y': 50, 'width': 60, 'height': 30},
    {'id': 'C-107', 'x': 600, 'y': 100, 'width': 40, 'height': 80},
]

connection_data = [
    ('T-100', 'P-102', 'pipe'),
    ('T-101', 'P-102', 'pipe'),
    ('P-102', 'V-104', 'pipe'),
    ('P-103', 'V-104', 'pipe'),
    ('V-104', 'E-105', 'pipe'),
    ('V-104', 'E-106', 'pipe'),
    ('E-105', 'C-107', 'pipe'),
    ('E-106', 'C-107', 'pipe'),
]

app = PIDEditor(equipment_data, connection_data)
app.mainloop()

