# -*- coding: utf-8 -*-
"""
ipad pointcloud streaming with open3d
by kentaroy47
"""

import numpy as np
import open3d as o3d
import cv2
from record3d import Record3DStream
from threading import Event

class DemoApp:
    def __init__(self):
        self.event = Event()
        self.session = None
        self.vis = o3d.visualization.VisualizerWithKeyCallback()
        self.vis.create_window()
        self.filter_enabled = False
        self.recording = False
        self.recorded_frames = []
        self.depth_trunc = 3.0
        self.live_voxel_size = 0.015
        self.save_voxel_size = 0.008
        self.record_every_n_frames = 3
        self.frame_count = 0
        self.running = True
        
    def on_new_frame(self):
        """
        This method is called from non-main thread, therefore cannot be used for presenting UI.
        """
        self.event.set()  # Notify the main thread to stop waiting and process new frame.

    def on_stream_stopped(self):
        print('Stream stopped')

    def connect_to_device(self, dev_idx):
        print('Searching for devices')
        devs = Record3DStream.get_connected_devices()
        print('{} device(s) found'.format(len(devs)))
        for dev in devs:
            print('\tID: {}\n\tUDID: {}\n'.format(dev.product_id, dev.udid))

        if len(devs) <= dev_idx:
            raise RuntimeError('Cannot connect to device #{}, try different index.'
                               .format(dev_idx))

        dev = devs[dev_idx]
        self.session = Record3DStream()
        self.session.on_new_frame = self.on_new_frame
        self.session.on_stream_stopped = self.on_stream_stopped
        self.session.connect(dev)  # Initiate connection and start capturing

    def get_intrinsic_mat_from_coeffs(self, coeffs):
        return np.array([[coeffs.fx,         0, coeffs.tx],
                         [        0, coeffs.fy, coeffs.ty],
                         [        0,         0,         1]])

    def create_point_cloud(self):
        depth = self.session.get_depth_frame()
        rgb = cv2.resize(self.session.get_rgb_frame(), np.flip(np.shape(depth)))
        rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(o3d.geometry.Image(rgb),
                                                                  o3d.geometry.Image(depth),
                                                                  depth_scale=1.0,
                                                                  depth_trunc=self.depth_trunc,
                                                                  convert_rgb_to_intensity=False)
        pcd = o3d.geometry.PointCloud.create_from_rgbd_image(rgbd, self.intrinsic)

        # Open3D uses a camera coordinate frame with Y down. Flip Y/Z so the
        # stream appears upright and faces the viewer naturally.
        pcd.transform([[1, 0, 0, 0],
                       [0, -1, 0, 0],
                       [0, 0, -1, 0],
                       [0, 0, 0, 1]])
        return pcd

    def save_point_cloud(self, pcd, filename="captured_pointcloud.ply"):
        o3d.io.write_point_cloud(filename, pcd)
        
    def record_frame(self, pcd):
        if self.recording and self.frame_count % self.record_every_n_frames == 0:
            self.recorded_frames.append(o3d.geometry.PointCloud(pcd))
    
    def save_recording(self, filename="recording.ply"):
        if self.recorded_frames:
            # Combine all frames into one point cloud
            combined = self.recorded_frames[0]
            for frame in self.recorded_frames[1:]:
                combined += frame

            print("Cleaning recorded point cloud...")
            combined = combined.voxel_down_sample(voxel_size=self.save_voxel_size)
            combined, _ = combined.remove_statistical_outlier(nb_neighbors=30, std_ratio=1.5)
            self.save_point_cloud(combined, filename)
            self.recorded_frames = []
            print(f"Saved {filename}")
        else:
            print("No recorded frames to save")

    def process_point_cloud(self, pcd):
        if self.filter_enabled:
            # Keep live filtering lightweight so streaming stays responsive.
            pcd = pcd.voxel_down_sample(voxel_size=self.live_voxel_size)
        
        return pcd
    
    def start_processing_stream(self):
        self.event.wait()  # Wait for new frame to arrive
        
        # get intrinsic parameters
        intrinsic_mat = self.get_intrinsic_mat_from_coeffs(self.session.get_intrinsic_mat())

        # setup point clouds
        # lidar depth map = 256x192
        # intrinsics work well divided by 4 than the given value from record3d
        self.intrinsic = o3d.camera.PinholeCameraIntrinsic(*np.shape(self.session.get_depth_frame()),
                                                           intrinsic_mat[0,0]/4,
                                                           intrinsic_mat[1,1]/4,
                                                           intrinsic_mat[0,2]/4,
                                                           intrinsic_mat[1,2]/4)
        self.pcd = self.create_point_cloud()
        # add geometry
        self.vis.add_geometry(self.pcd)

        # Add key callbacks for controls
        def toggle_filtering(vis):
            self.filter_enabled = not self.filter_enabled
            print(f"Filtering: {'enabled' if self.filter_enabled else 'disabled'}")
            return False

        def toggle_recording(vis):
            self.recording = not self.recording
            if self.recording:
                self.recorded_frames = []
                self.frame_count = 0
            print(f"Recording: {'started' if self.recording else 'stopped'}")
            return False

        def save_current_frame(vis):
            self.save_point_cloud(self.pcd)
            print("Frame saved")
            return False

        def end_recording(vis):
            self.recording = False
            self.save_recording()
            print("Recording saved")
            return False

        def quit_app(vis):
            self.running = False
            vis.close()
            return False

        self.vis.register_key_callback(ord("F"), toggle_filtering)
        self.vis.register_key_callback(ord("R"), toggle_recording)
        self.vis.register_key_callback(ord("S"), save_current_frame)
        self.vis.register_key_callback(ord("E"), end_recording)
        self.vis.register_key_callback(ord("Q"), quit_app)
        
        # Loop for point clouds
        while self.running:
            self.event.wait()  # Wait for new frame to arrive
            self.frame_count += 1

            # update pointclouds
            pcd = self.create_point_cloud()
            pcd = self.process_point_cloud(pcd)

            # Update visualization
            self.pcd.points = pcd.points
            self.pcd.colors = pcd.colors

            # Record the newest processed frame if enabled
            self.record_frame(self.pcd)
            
            # update geometry
            self.vis.update_geometry(self.pcd)
            self.running = self.vis.poll_events()
            self.vis.update_renderer()
    
            # close connection
            self.event.clear()

        self.vis.destroy_window()

if __name__ == '__main__':
    getter = DemoApp()
    getter.connect_to_device(dev_idx=0)
    getter.start_processing_stream()
