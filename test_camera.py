import cv2
import sys

print("🔍 Testing camera access...")

# Test different camera indices
for i in range(5):
    print(f"\n📹 Testing camera index {i}:")
    try:
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                print(f"✅ Camera {i} working! Frame shape: {frame.shape}")
                
                # Show camera info
                width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                fps = cap.get(cv2.CAP_PROP_FPS)
                print(f"   Resolution: {width}x{height}, FPS: {fps}")
                
                # Save a test frame
                cv2.imwrite(f'test_frame_{i}.jpg', frame)
                print(f"   Test frame saved as test_frame_{i}.jpg")
                
                cap.release()
                break
            else:
                print(f"❌ Camera {i} opened but can't read frame")
                cap.release()
        else:
            print(f"❌ Camera {i} failed to open")
    except Exception as e:
        print(f"❌ Camera {i} error: {e}")

print("\n🔍 Camera test complete!")

# Check system camera permissions
print("\n📋 System Info:")
print(f"OpenCV version: {cv2.__version__}")
print(f"Python version: {sys.version}")

# List available backends
backends = [cv2.CAP_AVFOUNDATION, cv2.CAP_V4L2, cv2.CAP_DSHOW]
backend_names = ['AVFoundation (macOS)', 'V4L2 (Linux)', 'DirectShow (Windows)']

print("\n🔧 Testing backends:")
for backend, name in zip(backends, backend_names):
    try:
        cap = cv2.VideoCapture(0, backend)
        if cap.isOpened():
            print(f"✅ {name} works")
            cap.release()
        else:
            print(f"❌ {name} failed")
    except:
        print(f"❌ {name} not available")