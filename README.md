# Clay-Create

Human in the loop system to work with Clay.

## iPad/iPhone LiDAR Point Cloud Streaming

Stream Apple LiDAR data from an iPad Pro or iPhone Pro with Open3D.

The script uses [record3d](https://github.com/marek-simonik/record3d) to stream RGB-D data and visualizes the live point cloud with Open3D.

## Installation

1. Install the Python dependencies:

```bash
pip install -r requirements.txt
```

2. Install the [Record3D app](https://record3d.app/) on your Apple device.

## Usage

1. Connect your Apple device to the computer with a USB cable.
2. Launch the Record3D app on your device.
3. Run the streaming script:

```bash
python ipad_stream.py
```

## Keyboard Controls

* `F`: Toggle point cloud filtering
* `R`: Start/stop recording
* `S`: Save current frame
* `E`: End recording and save combined point cloud
* `Q`: Quit

## Output

* Individual frames are saved as PLY files.
* Recordings are combined into one PLY file.
