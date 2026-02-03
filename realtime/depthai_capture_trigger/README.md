# DepthAI Motion Detection Capture System

A Python-based system that uses DepthAI v2 to stream camera images, detect moving objects in a predefined region of interest (ROI), and automatically capture images when motion is detected.

## Features

- **Real-time Motion Detection**: Uses frame differencing to detect moving objects
- **Adjustable ROI**: Define a specific area to monitor for motion
- **Automatic Image Capture**: Saves images when motion is detected in the ROI
- **Live Preview**: Visual feedback showing ROI, detected motion, and capture status
- **Interactive ROI Editor**: Easy-to-use tool to adjust the detection area
- **Configurable Parameters**: Fine-tune sensitivity and behavior via JSON config

## Requirements

- DepthAI-compatible camera (OAK-D, OAK-1, etc.)
- Python 3.7+
- See `requirements.txt` for package dependencies

## Installation

1. Clone or download this repository

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Verify DepthAI installation:
```bash
python -c "import depthai; print(depthai.__version__)"
```

## Usage

### 1. Configure ROI (First Time Setup)

Run the ROI editor to define your detection area:

```bash
python roi_editor.py
```

**Instructions:**
- Click and drag on the video feed to draw a rectangle
- The green rectangle shows the current ROI
- Yellow rectangle shows your selection in progress
- Press **'s'** to save the ROI to `config.json`
- Press **'r'** to reset to default (center 50%)
- Press **'q'** to quit

### 2. Run Motion Capture

Start the motion detection and capture system:

```bash
python motion_capture.py
```

**Instructions:**
- The system will display a live camera feed
- Green ROI rectangle = no motion detected
- Red ROI rectangle = motion detected in ROI
- Yellow boxes = detected motion areas
- Images are automatically saved to the `captures/` directory
- Press **'r'** to reload config without restarting
- Press **'q'** to quit

## Configuration

Edit `config.json` to customize behavior:

### Camera Settings
```json
"camera": {
  "resolution": "1080p",  // Options: "1080p", "4k", "12mp"
  "fps": 30               // Frames per second
}
```

### ROI Settings
```json
"roi": {
  "x1": 0.25,  // Left edge (0-1, normalized)
  "y1": 0.25,  // Top edge (0-1, normalized)
  "x2": 0.75,  // Right edge (0-1, normalized)
  "y2": 0.75   // Bottom edge (0-1, normalized)
}
```
*Note: Use the ROI editor instead of manually editing these values*

### Motion Detection Settings
```json
"motion_detection": {
  "threshold": 25,           // Sensitivity (lower = more sensitive, 0-255)
  "min_contour_area": 500,   // Minimum size in pixels for valid motion
  "gaussian_blur_kernel": 21 // Noise reduction (must be odd number)
}
```

**Tuning tips:**
- **threshold**: Start with 25. Decrease for more sensitivity, increase to reduce false positives
- **min_contour_area**: Larger values ignore small movements (e.g., leaves, insects)
- **gaussian_blur_kernel**: Larger values reduce noise but may miss small objects

### Capture Settings
```json
"capture": {
  "output_dir": "captures",    // Directory for saved images
  "image_format": "jpg",       // Format: "jpg", "png", "bmp"
  "quality": 95,               // JPEG quality (1-100)
  "cooldown_seconds": 1.0      // Minimum time between captures
}
```

**Cooldown** prevents capturing multiple images of the same motion event. Increase for slower-moving objects.

## Output

Captured images are saved with timestamps:
```
captures/capture_20260127_163045_123_0001.jpg
                 YYYYMMDD_HHMMSS_ms__count
```

## Troubleshooting

### Camera Not Found
```
RuntimeError: Failed to find device
```
**Solution**: Ensure your DepthAI camera is connected via USB 3.0

### No Motion Detected
- Check ROI covers the area where motion occurs (use ROI editor)
- Decrease `threshold` in config.json (e.g., try 15-20)
- Decrease `min_contour_area` for smaller objects
- View the "Motion Detection - Threshold" window to see what the system detects

### Too Many False Captures
- Increase `threshold` (e.g., 30-40)
- Increase `min_contour_area` to ignore small movements
- Increase `cooldown_seconds`
- Reduce ROI size to focus on specific area

### Performance Issues
- Lower camera resolution (e.g., from "4k" to "1080p")
- Decrease FPS
- Increase `gaussian_blur_kernel` (but use odd numbers: 21, 25, 29)

## How It Works

1. **Frame Capture**: DepthAI camera streams video frames
2. **Preprocessing**: Frames are converted to grayscale and blurred
3. **Frame Differencing**: Current frame is compared to previous frame
4. **Thresholding**: Pixel differences above threshold indicate motion
5. **Contour Detection**: Connected motion pixels are grouped into contours
6. **ROI Check**: System checks if contours intersect with ROI
7. **Capture**: If motion in ROI and cooldown expired, image is saved

## Files

- `motion_capture.py` - Main motion detection and capture script
- `roi_editor.py` - Interactive ROI configuration tool
- `config.json` - Configuration file (created on first run)
- `requirements.txt` - Python dependencies
- `captures/` - Output directory for captured images (created automatically)

## License

This project is provided as-is for educational and research purposes.

## Support

For issues with:
- **DepthAI library**: Visit [Luxonis Docs](https://docs.luxonis.com/)
- **This implementation**: Check configuration settings and adjust parameters
