import open3d as o3d
import numpy as np
from pathlib import Path


# -----------------------------
# Settings
# -----------------------------

INPUT_FILE = "data/cloud.ply"
OUTPUT_CLEAN_CLOUD = "output/clean_object.ply"

VOXEL_SIZE = 0.02

NB_NEIGHBORS = 30
STD_RATIO = 1.2

FLOOR_DISTANCE_THRESHOLD = 0.015


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
    print("Removing floor plane...")

    plane_model, inliers = pcd.segment_plane(
        distance_threshold=FLOOR_DISTANCE_THRESHOLD,
        ransac_n=3,
        num_iterations=1000
    )

    pcd_without_floor = pcd.select_by_index(
        inliers,
        invert=True
    )

    print(f"After floor removal: {len(pcd_without_floor.points)} points")

    return pcd_without_floor


def crop_object_by_height(pcd):
    print("Cropping object by height...")

    points = np.asarray(pcd.points)

    z_min = points[:, 2].min()
    z_max = points[:, 2].max()

    print(f"Z min: {z_min}")
    print(f"Z max: {z_max}")

    # kõrguse cutoff
    height_cut = z_min + 0.08

    indices = np.where(points[:, 2] > height_cut)[0]

    object_cloud = pcd.select_by_index(indices)

    print(f"Object points: {len(object_cloud.points)}")

    return object_cloud


def create_bounding_box(pcd):
    print("Creating bounding box...")

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