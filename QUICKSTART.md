# Quick Start Guide - iPixel LED Controller

## 🚀 Quick Installation (Windows)

### Step 1: Install Python
1. Download Python from: https://www.python.org/downloads/
2. **IMPORTANT**: During installation, check ☑️ "Add Python to PATH"
3. Complete the installation

### Step 2: Download the Application
1. Download all files to a folder (e.g., `C:\iPixel`)
2. You should have these files:
   - `ipixel_controller.py`
   - `requirements.txt`
   - `run.bat`
   - `README.md`

### Step 3: Run the Application
1. Double-click `run.bat` in the folder
2. First time: It will automatically install dependencies (takes 1-2 minutes)
3. The application window will open

### Step 4: Connect Your LED Panel
1. Turn on your iPixel LED panel
2. In the app, click **"Scan"**
3. Select your device (usually "LED_BLE_...")
4. Click **"Connect"**
5. Wait for green "Connected" status

### Step 5: Start Using It!
- **Text Tab**: Send custom text with colors
- **Image Tab**: Display images
- **Clock Tab**: Show time
- **📈 Stock Tab**: Live stock market prices
- **📺 YouTube Tab**: Channel statistics (requires API key)
- **🌤️ Weather Tab**: Current weather conditions (requires API key)
- **🎨 Animations Tab**: Pixel art animations (Game of Life, Matrix, Fire, etc.)
- **Settings Tab**: Adjust brightness and power

## 🔧 Alternative: Manual Installation

If `run.bat` doesn't work, follow these steps:

1. Open Command Prompt (Win+R, type `cmd`, press Enter)

2. Navigate to your folder:
   ```
   cd C:\iPixel
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Run the application:
   ```
   python ipixel_controller.py
   ```

## ❗ Troubleshooting

### "Python is not recognized"
- You didn't check "Add Python to PATH" during installation
- Solution: Reinstall Python and make sure to check that box

### "pip is not recognized"
- Reinstall Python with "Add Python to PATH" checked
- Or use: `python -m pip install -r requirements.txt`

### Device Not Found
- Panel must be powered on
- Close official iPixel app if running
- Try scanning again
- Move panel closer to PC

### Connection Timeout
- Remove device from Windows Bluetooth settings first
- Then scan and connect through the app
- Make sure no other device is connected to the panel

### Import Errors
- Run: `pip install pypixelcolor bleak pillow`
- Restart the application

## 📝 Quick Tips

1. **First connection** may take 10-20 seconds
2. **Keep panel close** to PC for best connection
3. **Short text** displays better on small panels
4. **Image resolution**: Match your panel size for best results
5. **Brightness**: Start at 50% and adjust

## 🎯 Common Panel Sizes

- **64x64 pixels**: Good for images and detailed text
- **32x32 pixels**: Suitable for short text and simple images
- **96x16 pixels**: Perfect for scrolling text
- **20x64 pixels**: Wide format for text

## 🔥 New Features Guide

### Stock Market Display
1. Go to **📈 Stock** tab
2. Enter ticker (AAPL, TSLA, etc.)
3. Click "Fetch Stock Data"
4. Customize colors and format
5. Click "Send to Display"
6. Enable auto-refresh for live updates

**No API key needed!**

### YouTube Stats
1. Get free API key from [Google Cloud Console](https://console.cloud.google.com/)
2. Go to **📺 YouTube** tab
3. Enter and save API key
4. Enter channel @handle or ID
5. Click "Fetch Stats"
6. Choose display format
7. Click "Send to Display"

### Weather Display
1. Get free API key from [OpenWeatherMap](https://openweathermap.org/api)
2. Go to **🌤️ Weather** tab
3. Enter and save API key
4. Enter your city name
5. Select °C or °F
6. Click "Fetch Weather"
7. Click "Send to Display"

### Pixel Art Animations
1. Go to **🎨 Animations** tab
2. Choose animation type:
   - **Game of Life**: Classic cellular automaton
   - **Matrix**: Digital rain effect
   - **Fire**: Realistic fire simulation
   - **Starfield**: Moving stars
   - **Plasma**: Colorful plasma waves
3. Select color scheme and FPS
4. Click "Start Animation"

**Pro tip**: Save your favorite configs as presets!

## 🆘 Need Help?

1. Check the full README.md for detailed instructions
2. Verify Bluetooth is enabled on your PC
3. Make sure panel is charged/powered
4. Try restarting both panel and PC
5. Update Python to the latest version

## ✅ System Requirements

- Windows 10 or 11
- Python 3.8 or higher
- Bluetooth LE adapter
- 50 MB free disk space

---

**You're all set! Enjoy your LED panel! 🎨**
