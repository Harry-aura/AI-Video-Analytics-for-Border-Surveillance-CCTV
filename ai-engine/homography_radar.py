"""
IBVAP Defense-Grade V2 - Decoupled Sector Tactical Radar Projector
Calculates sector-specific planar ground-plane projections for each camera independently.
Provides:
1. render_sector_scope(): High-contrast tactical radar mini-scope for an individual camera sector.
2. render_multi_sector_grid(): 4-Quadrant Decoupled Multi-Sector Tactical Display (800x600).
3. render_radar_canvas(): Unified interface supporting 4-Sector Grid or Single Sector Focus.
"""
import cv2
import math
import numpy as np

SECTOR_CONFIGS = {
    'CAM-01': {
        'code': 'SECTOR-A',
        'name': 'North Perimeter Gate',
        'heading_deg': 0,
        'color': (0, 255, 200),  # Cyan
        'range_m': 40
    },
    'CAM-02': {
        'code': 'SECTOR-B',
        'name': 'Sector 4 Perimeter Wire',
        'heading_deg': 90,
        'color': (0, 200, 255),  # Amber-Gold
        'range_m': 40
    },
    'CAM-03': {
        'code': 'SECTOR-C',
        'name': 'Buffer Zone Approach',
        'heading_deg': 180,
        'color': (255, 200, 0),  # Yellow
        'range_m': 40
    },
    'CAM-04': {
        'code': 'SECTOR-D',
        'name': 'Vehicle Checkpoint & ANPR',
        'heading_deg': 270,
        'color': (200, 100, 255), # Magenta
        'range_m': 40
    }
}

class HomographyRadarProjector:
    def __init__(self, map_width: int = 800, map_height: int = 600):
        self.map_width = map_width
        self.map_height = map_height

    def project_foot_coordinate(self, camera_id: str, bbox: list, scope_w: int = 400, scope_h: int = 300) -> tuple:
        """
        Projects foot contact point ((x1+x2)/2, y2) from 640x480 screen space
        into the camera sector's ground-plane radar space.
        Radar origin (camera sensor position) is at (scope_w // 2, scope_h - 25).
        """
        x1, y1, x2, y2 = bbox
        foot_x = (x1 + x2) / 2.0
        foot_y = float(y2)  # Ground contact point (0 at top, 480 at bottom/near)

        # Normalize screen coordinates:
        # Screen X (0 to 640) -> Normalized azimuth (-1.0 to +1.0)
        norm_x = (foot_x - 320.0) / 320.0
        
        # Screen Y (0 to 480): y=480 is camera baseline (distance=3m), y=0 is far horizon (distance=40m)
        norm_dist = max(0.05, (480.0 - foot_y) / 480.0)

        # Map to sector radar polar fan
        origin_x = scope_w // 2
        origin_y = scope_h - 25
        max_radar_r = scope_h - 55

        radar_r = norm_dist * max_radar_r
        # Azimuth fan angle (Field of view approx 70 degrees: -35 to +35 deg from optical axis)
        azimuth_rad = norm_x * math.radians(35.0)

        radar_x = int(origin_x + radar_r * math.sin(azimuth_rad))
        radar_y = int(origin_y - radar_r * math.cos(azimuth_rad))

        radar_x = int(np.clip(radar_x, 8, scope_w - 8))
        radar_y = int(np.clip(radar_y, 8, scope_h - 8))
        return radar_x, radar_y

    def project_point(self, camera_id: str, x: float, y: float, scope_w: int = 400, scope_h: int = 300) -> tuple:
        """Projects a 2D point (x, y) into radar ground-plane space."""
        return self.project_foot_coordinate(camera_id, [x, y, x, y], scope_w, scope_h)

    def project_fence_points(self, camera_id: str, fence_points: list, scope_w: int = 400, scope_h: int = 300) -> list:
        """
        Projects screen-space fence coordinates [[x, y], ...] onto the sector radar ground plane.
        """
        if not fence_points:
            return []
        out = []
        for pt in fence_points:
            rx, ry = self.project_foot_coordinate(camera_id, [pt[0], pt[1], pt[0], pt[1]], scope_w, scope_h)
            out.append((rx, ry))
        return out

    def render_sector_scope(self, camera_id: str, camera_name: str, active_targets: list,
                            fence_data: dict = None, scope_size: tuple = (400, 300),
                            acoustic_vectors: list = None) -> np.ndarray:
        """
        Renders a decoupled, standalone tactical radar mini-scope for a specific camera sector.
        """
        w, h = scope_size
        scope = np.zeros((h, w, 3), dtype=np.uint8)
        scope[:] = (13, 17, 23)  # Dark Tactical Navy

        sec_info = SECTOR_CONFIGS.get(camera_id, {
            'code': camera_id,
            'name': camera_name,
            'heading_deg': 0,
            'color': (0, 255, 200),
            'range_m': 40
        })

        origin_x = w // 2
        origin_y = h - 25
        max_r = h - 55

        # 1. Concentric Distance Range Rings (10m, 20m, 30m, 40m)
        num_rings = 4
        for i in range(1, num_rings + 1):
            r = int(max_r * (i / float(num_rings)))
            dist_label = f"{(40 // num_rings) * i}m"
            cv2.ellipse(scope, (origin_x, origin_y), (r, r), 0, 215, 325, (32, 44, 58), 1, cv2.LINE_AA)
            cv2.putText(scope, dist_label, (origin_x + 6, origin_y - r + 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.28, (65, 85, 105), 1)

        # 2. Azimuth Radial Lines (-35°, 0°, +35°)
        for deg in [-35, -17.5, 0, 17.5, 35]:
            rad = math.radians(deg)
            ex = int(origin_x + max_r * math.sin(rad))
            ey = int(origin_y - max_r * math.cos(rad))
            line_color = (45, 60, 80) if deg != 0 else (60, 90, 120)
            cv2.line(scope, (origin_x, origin_y), (ex, ey), line_color, 1, cv2.LINE_AA)

        # 3. Camera Origin Node
        cam_color = sec_info['color']
        cv2.circle(scope, (origin_x, origin_y), 6, cam_color, -1)
        cv2.circle(scope, (origin_x, origin_y), 9, (255, 255, 255), 1)

        # 4. Render Projected Fence Line
        if fence_data:
            f_pts = fence_data.get('points', [])
            b_mode = fence_data.get('mode', 'OPEN_LINE')
            if len(f_pts) >= 2:
                proj_fence = self.project_fence_points(camera_id, f_pts, w, h)
                if len(proj_fence) >= 2:
                    if b_mode == 'CLOSED_POLYGON' and len(proj_fence) >= 3:
                        poly_arr = np.array(proj_fence, dtype=np.int32).reshape((-1, 1, 2))
                        cv2.polylines(scope, [poly_arr], isClosed=True, color=(0, 140, 255), thickness=2, lineType=cv2.LINE_AA)
                    else:
                        for i in range(len(proj_fence) - 1):
                            cv2.line(scope, proj_fence[i], proj_fence[i+1], (0, 140, 255), 2, cv2.LINE_AA)
                    for pt in proj_fence:
                        cv2.circle(scope, pt, 4, (0, 255, 255), -1)

        # 5. Render Intruder Target Blips for this specific camera (Strict Zero-Bleed Isolation)
        cam_targets = [t for t in active_targets if t.get('camera_id') == camera_id]
        for target in cam_targets:
            box = target.get('box')
            if not box:
                continue
            rx, ry = self.project_foot_coordinate(camera_id, box, w, h)
            
            gid = target.get('global_id', 0)
            cls_name = target.get('cls_name', 'TARGET')
            iff = target.get('iff_status', 'UNKNOWN')
            vx, vy = target.get('velocity', (0, 0))

            if iff == 'HOSTILE':
                blip_color = (0, 0, 255)  # Red
            elif iff == 'SUSPICIOUS':
                blip_color = (0, 165, 255)  # Amber
            elif iff == 'NEUTRAL_WILDLIFE':
                blip_color = (0, 255, 100)  # Green
            else:
                blip_color = (200, 200, 200)

            # Target Blip & Halo
            cv2.circle(scope, (rx, ry), 5, blip_color, -1)
            cv2.circle(scope, (rx, ry), 8, (255, 255, 255), 1)

            # Heading Vector
            if math.hypot(vx, vy) > 0.4:
                hx = int(rx + vx * 4.0)
                hy = int(ry + vy * 4.0)
                cv2.arrowedLine(scope, (rx, ry), (hx, hy), (0, 255, 255), 2, tipLength=0.35)

            # Target Tag
            tag = f"#{gid} {cls_name}"
            cv2.putText(scope, tag, (rx + 8, ry - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.32, blip_color, 1)

        # 6. Scope Header Banner
        cv2.rectangle(scope, (0, 0), (w, 24), (20, 26, 34), -1)
        cv2.putText(scope, f"{sec_info['code']}: {camera_name} (40m)", (8, 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, cam_color, 1)
        
        # Outer Scope Border
        cv2.rectangle(scope, (0, 0), (w - 1, h - 1), (40, 52, 68), 1)
        return scope

    def render_multi_sector_grid(self, camera_fences: dict = None, active_targets: list = None,
                                 acoustic_vectors: list = None, grid_size: tuple = (800, 600)) -> np.ndarray:
        """
        Combines 4 independent sector scopes into a 2x2 multi-sector radar display (800x600).
        """
        grid_w, grid_h = grid_size
        half_w = grid_w // 2
        half_h = grid_h // 2

        canvas = np.zeros((grid_h, grid_w, 3), dtype=np.uint8)

        cameras = [
            ('CAM-01', 'North Perimeter Gate', 0, 0),
            ('CAM-02', 'Sector 4 Perimeter Wire', half_w, 0),
            ('CAM-03', 'Buffer Zone Approach', 0, half_h),
            ('CAM-04', 'Vehicle Checkpoint & ANPR', half_w, half_h)
        ]

        active_targets = active_targets or []
        camera_fences = camera_fences or {}

        for cid, cname, ox, oy in cameras:
            # Filter targets strictly for this camera
            c_targets = [t for t in active_targets if t.get('camera_id') == cid]
            f_data = camera_fences.get(cid, {})
            
            scope = self.render_sector_scope(
                camera_id=cid,
                camera_name=cname,
                active_targets=c_targets,
                fence_data=f_data,
                scope_size=(half_w, half_h),
                acoustic_vectors=acoustic_vectors
            )
            canvas[oy:oy + half_h, ox:ox + half_w] = scope

        return canvas

    def render_radar_canvas(self, active_targets: list, acoustic_vectors: list = None,
                            camera_fences: dict = None, sector_focus: str = None) -> np.ndarray:
        """
        Main interface: renders 4-sector decoupled grid or single focused sector.
        """
        if sector_focus and sector_focus in SECTOR_CONFIGS:
            sec_info = SECTOR_CONFIGS[sector_focus]
            f_data = (camera_fences or {}).get(sector_focus, {})
            c_targets = [t for t in active_targets if t.get('camera_id') == sector_focus]
            return self.render_sector_scope(
                camera_id=sector_focus,
                camera_name=sec_info['name'],
                active_targets=c_targets,
                fence_data=f_data,
                scope_size=(self.map_width, self.map_height),
                acoustic_vectors=acoustic_vectors
            )
        else:
            return self.render_multi_sector_grid(
                camera_fences=camera_fences,
                active_targets=active_targets,
                acoustic_vectors=acoustic_vectors,
                grid_size=(self.map_width, self.map_height)
            )