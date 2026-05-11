import open3d as o3d
import numpy as np
from pathlib import Path


# -----------------------------
# Settings
# -----------------------------

INPUT_FILE = "data/auto_capture_20260509_120152.ply"
OUTPUT_CLEAN_CLOUD = "output/auto_capture_20260509_120152.ply"

VOXEL_SIZE = 0.003

NB_NEIGHBORS = 20
STD_RATIO = 2.0

REMOVE_FLOOR = True
FLOOR_DISTANCE_THRESHOLD = 0.015
OBJECT_HEIGHT_ABOVE_FLOOR = 0.006

CROP_BY_HEIGHT = False
HEIGHT_CROP_OFFSET = 0.08
MIN_REMAINING_POINTS = 100


# -----------------------------
# Functions
# -----------------------------

def load_point_cloud(path):
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    pcd = o3d.io.read_point_cloud(str(path))

    if pcd.is_empty():
        raise ValueError("Point cloud is empty.")

    print(f"Loaded {len(pcd.points)} points")
    return pcd


def downsample_point_cloud(pcd):
    print("Downsampling point cloud...")

    pcd_down = pcd.voxel_down_sample(
        voxel_size=VOXEL_SIZE
    )

    print(f"After downsampling: {len(pcd_down.points)} points")
    return pcd_down


def remove_noise(pcd):
    print("Removing statistical noise...")

    pcd_clean, _ = pcd.remove_statistical_outlier(
        nb_neighbors=NB_NEIGHBORS,
        std_ratio=STD_RATIO
    )

    print(f"After noise removal: {len(pcd_clean.points)} points")
    return pcd_clean


def remove_floor_plane(pcd):
    if not REMOVE_FLOOR:
        print("Skipping floor removal.")
        return pcd

    print("Removing floor plane...")

    plane_model, inliers = pcd.segment_plane(
        distance_threshold=FLOOR_DISTANCE_THRESHOLD,
        ransac_n=3,
        num_iterations=1000
    )

    a, b, c, d = plane_model
    points = np.asarray(pcd.points)
    signed_distances = points @ np.array([a, b, c]) + d

    positive_side = signed_distances > OBJECT_HEIGHT_ABOVE_FLOOR
    negative_side = signed_distances < -OBJECT_HEIGHT_ABOVE_FLOOR

    positive_z = points[positive_side, 2].mean() if positive_side.any() else -np.inf
    negative_z = points[negative_side, 2].mean() if negative_side.any() else -np.inf

    if negative_z > positive_z:
        signed_distances = -signed_distances

    object_indices = np.where(signed_distances > OBJECT_HEIGHT_ABOVE_FLOOR)[0]

    pcd_without_floor = pcd.select_by_index(object_indices)

    if len(pcd_without_floor.points) < MIN_REMAINING_POINTS:
        print("Floor removal left too few points; keeping original cloud.")
        return pcd

    print(f"Floor points detected: {len(inliers)}")
    print(f"After floor removal: {len(pcd_without_floor.points)} points")

    return pcd_without_floor


def crop_object_by_height(pcd):
    if not CROP_BY_HEIGHT:
        print("Skipping height crop.")
        return pcd

    print("Cropping object by height...")

    points = np.asarray(pcd.points)

    z_min = points[:, 2].min()
    z_max = points[:, 2].max()

    print(f"Z min: {z_min}")
    print(f"Z max: {z_max}")

    # kõrguse cutoff
    z_range = z_max - z_min

    if z_range <= HEIGHT_CROP_OFFSET:
        print("Cloud is shorter than height crop offset; skipping height crop.")
        return pcd

    height_cut = z_min + HEIGHT_CROP_OFFSET

    indices = np.where(points[:, 2] > height_cut)[0]

    object_cloud = pcd.select_by_index(indices)

    if len(object_cloud.points) < MIN_REMAINING_POINTS:
        print("Height crop left too few points; keeping original cloud.")
        return pcd

    print(f"Object points: {len(object_cloud.points)}")

    return object_cloud


def create_bounding_box(pcd):
    print("Creating bounding box...")

    if len(pcd.points) < 4:
        raise ValueError("Need at least 4 points to create a 3D bounding box.")

    bbox = pcd.get_oriented_bounding_box()
    bbox.color = (1, 0, 0)

    return bbox


def save_point_cloud(pcd, output_path):
    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    o3d.io.write_point_cloud(
        str(output_path),
        pcd
    )

    print(f"Saved point cloud: {output_path}")


def preview_result(object_cloud, bbox):
    print("Opening preview window...")

    o3d.visualization.draw_geometries(
        [
            object_cloud,
            bbox
        ],
        window_name="Cleaned Object"
    )


# -----------------------------
# Main
# -----------------------------

def main():
    pcd = load_point_cloud(INPUT_FILE)

    pcd = downsample_point_cloud(pcd)

    pcd = remove_noise(pcd)

    pcd = remove_floor_plane(pcd)

    object_cloud = crop_object_by_height(pcd)

    bbox = create_bounding_box(object_cloud)

    save_point_cloud(
        object_cloud,
        OUTPUT_CLEAN_CLOUD
    )

    preview_result(
        object_cloud,
        bbox
    )


if __name__ == "__main__":
    main()
