from pathlib import Path
import open3d as o3d
import numpy as np

# PATHS
base_dir = Path(__file__).parent

input_path = base_dir / "data" / "last.ply"
output_path = base_dir / "output" / "last_mesh.obj"

output_path.parent.mkdir(exist_ok=True)

# LOAD
print("Loading point cloud...")
pcd = o3d.io.read_point_cloud(str(input_path))

# SCALE
scale_factor = 1000
pcd.scale(scale_factor, center=(0, 0, 0))

print("Point count:", len(pcd.points))

if len(pcd.points) == 0:
    raise ValueError("Point cloud is empty")

# SCALE INFO
bbox = pcd.get_axis_aligned_bounding_box()
scale = np.linalg.norm(bbox.get_extent())

# SETTINGS
voxel_size = scale / 350
normal_radius = scale / 60

# DOWNSAMPLE
print("Downsampling...")
pcd = pcd.voxel_down_sample(voxel_size)

# OUTLIER REMOVAL
print("Removing outliers...")
pcd, _ = pcd.remove_statistical_outlier(
    nb_neighbors=30,
    std_ratio=1.5
)

# NORMALS
print("Estimating normals...")
pcd.estimate_normals(
    search_param=o3d.geometry.KDTreeSearchParamHybrid(
        radius=normal_radius,
        max_nn=50
    )
)

try:
    pcd.orient_normals_consistent_tangent_plane(50)
except Exception as e:
    print("Normal orientation skipped:", e)

# POISSON
print("Generating mesh...")
mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
    pcd,
    depth=9
)

# DENSITY CLEANUP
print("Cleaning mesh...")

densities = np.asarray(densities)
density_threshold = np.quantile(densities, 0.05)

vertices_to_remove = densities < density_threshold
mesh.remove_vertices_by_mask(vertices_to_remove)

# REMOVE SMALL FLOATING COMPONENTS
triangle_clusters, cluster_n_triangles, cluster_area = (
    mesh.cluster_connected_triangles()
)

triangle_clusters = np.asarray(triangle_clusters)
cluster_n_triangles = np.asarray(cluster_n_triangles)

min_triangles = 5000
triangles_to_remove = cluster_n_triangles[triangle_clusters] < min_triangles

mesh.remove_triangles_by_mask(triangles_to_remove)
mesh.remove_unreferenced_vertices()

# FINAL CLEANUP
mesh.remove_degenerate_triangles()
mesh.remove_duplicated_triangles()
mesh.remove_duplicated_vertices()
mesh.remove_non_manifold_edges()
mesh.remove_unreferenced_vertices()

# SMOOTH EDGES / SURFACE
print("Smoothing mesh...")
mesh = mesh.filter_smooth_simple(number_of_iterations=2)

# CLEAN AGAIN AFTER SMOOTH
mesh.remove_degenerate_triangles()
mesh.remove_duplicated_triangles()
mesh.remove_duplicated_vertices()
mesh.remove_non_manifold_edges()
mesh.remove_unreferenced_vertices()

mesh.compute_vertex_normals()

# SAVE
print("Saving OBJ...")
o3d.io.write_triangle_mesh(str(output_path), mesh)

print("DONE")
print(output_path)