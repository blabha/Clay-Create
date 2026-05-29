import argparse
import open3d as o3d
import numpy as np
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--input",  required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()

input_path  = Path(args.input)
output_path = Path(args.output)
output_path.parent.mkdir(parents=True, exist_ok=True)

print("Loading point cloud...")
pcd = o3d.io.read_point_cloud(str(input_path))

print("Point count:", len(pcd.points))

if len(pcd.points) == 0:
    raise ValueError("Point cloud is empty")

# SCALE
bbox = pcd.get_axis_aligned_bounding_box()
scale = np.linalg.norm(bbox.get_extent())

# AUTO SETTINGS
voxel_size = scale / 300
normal_radius = scale / 80

print("Downsampling...")
pcd = pcd.voxel_down_sample(voxel_size)

print("Removing outliers...")
pcd, _ = pcd.remove_statistical_outlier(
    nb_neighbors=20,
    std_ratio=2.0
)

print("Estimating normals...")
pcd.estimate_normals(
    search_param=o3d.geometry.KDTreeSearchParamHybrid(
        radius=normal_radius,
        max_nn=40
    )
)

try:
    pcd.orient_normals_consistent_tangent_plane(30)
except Exception as e:
    print("Normal orientation skipped:", e)

print("Generating mesh...")
mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
    pcd,
    depth=9
)

print("Cleaning mesh...")

densities = np.asarray(densities)
threshold = np.quantile(densities, 0.03)

vertices_to_remove = densities < threshold
mesh.remove_vertices_by_mask(vertices_to_remove)

mesh.remove_degenerate_triangles()
mesh.remove_duplicated_triangles()
mesh.remove_duplicated_vertices()
mesh.remove_non_manifold_edges()

mesh.compute_vertex_normals()

print("Saving OBJ...")
o3d.io.write_triangle_mesh(str(output_path), mesh)

print("DONE")
print(output_path)