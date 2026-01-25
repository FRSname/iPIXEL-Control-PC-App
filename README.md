# iPixel LED Panel Controller

A desktop application to control iPixel Color LED matrix displays (like BGLight, B.K. Light LED Pixel Board) directly from your Windows PC via Bluetooth.

![iPixel Controller](screenshot.png)

## 🚀 Quick Start

**New users?** Read [INSTALL.md](INSTALL.md) or [START_HERE.txt](START_HERE.txt) for step-by-step instructions!

### Installation (3 steps)

1. **Install Python 3.8+** from [python.org](https://www.python.org/downloads/)
   - ⚠️ Check "Add Python to PATH" during installation!

2. **Install dependencies:**
   ```bash
   python -m pip install -r requirements.txt
   ```

3. **Launch the app:**
   ```bash
   python run.py
   ```
   Or simply double-click `run.py`

**Note:** Use `run.py` instead of `run.bat` - Python files aren't blocked by Windows Smart App Control!

### API Keys (stored separately)

API keys are stored in `ipixel_secrets.json` (gitignored). Add keys via the app UI (YouTube/Weather tabs) and they will be saved there.

## Features

### Core Features
- 🔍 **Auto-scan** for iPixel devices via Bluetooth
- 📝 **Send text** with customizable text color, background color, and sprite fonts
- 🖼️ **Display images** (PNG, JPG, GIF, BMP) with thumbnail previews
- 🕐 **Clock mode** with built-in styles, custom time formats, and countdown timers
- 💾 **Preset system** - Save and quickly execute your favorite configurations
- 💡 **Brightness control** (1-100%)
- ⚡ **Power control** (ON/OFF)
- 🎨 **Color picker** for text and background
- 🖥️ **Easy-to-use GUI** built with Tkinter

### Advanced Features

#### 📈 Stock Market Display
Display live stock prices directly on your LED panel! 
- **No API key required** - Uses free yfinance library
- Support for any stock ticker (AAPL, TSLA, BTC-USD, etc.)
- Auto-refresh with configurable intervals
- Smart price formatting (auto-adjusts decimals, uses K notation for large numbers)
- Auto-color based on price movement (green=up, red=down)
- Multiple display formats (with static cycling for some formats)

#### 📺 YouTube Stats
Show your YouTube channel subscribers with an optional inline logo.
- Works with channel IDs or @handles
- Auto-refresh capability
- Smart number formatting (1.2M, 450K, etc.)
- **Format:** Logo + Subscribers only
- **Logo requirement:** 14x16 PNG (auto-resized if needed)
- **Requires:** YouTube Data API v3 key (stored in `ipixel_secrets.json`)

#### 🌤️ Weather Display
Show current weather conditions and temperature!
- Real-time weather data from OpenWeatherMap
- Support for any city worldwide
- Temperature in Celsius or Fahrenheit
- Display current temperature, condition, feels-like, humidity
- Auto-refresh with configurable intervals
- Multiple display formats:
  - Temperature + Condition (e.g., "72°F Sunny")
  - Temperature only
  - City + Temperature
  - Full info
- **Requires:** Free OpenWeatherMap API key (stored in `ipixel_secrets.json`)
- **Quota:** 1,000 calls/day, updates every 10 minutes (free tier)

#### 🎨 Pixel Art Animations
Generate and display procedural pixel art animations!
- **Conway's Game of Life**: Classic cellular automaton with emergent patterns
  - Adjustable initial density (10-50%)
  - Watch patterns evolve in real-time
- **Matrix Rain**: Digital rain effect inspired by The Matrix
  - Falling character trails with fade effect
- **Fire Effect**: Realistic fire simulation
  - Heat propagation algorithm
  - Red-orange-yellow gradient
- **Starfield**: Parallax scrolling stars
  - 3 speed levels for depth perception
- **Plasma**: Colorful interference patterns
  - Sine wave-based smooth animations
- Configurable FPS (1-30, recommended 10-20 for best results)
- Color schemes: White, Green, Blue, Red, Rainbow
- Duration control (set seconds or infinite loop)
- **No API key required**

## Requirements

- Windows 10/11 (with Bluetooth LE support)
- Python 3.8 or higher
- Bluetooth adapter (built-in or USB dongle)
- iPixel Color LED panel (BGLight, B.K. Light, etc.)

## Hardware Limitations

- **Background color brightness:** On some iPixel panels/firmware versions, the background color rendered by the built-in text command appears dim or near-black, even when set to bright colors (e.g., white). This is a **device/firmware limitation**, not a color picker bug in the app.
- **Workaround:** If you need a truly bright background, use a full-image preset (or a custom image) where the background is part of the image itself. The original vendor app may use different commands or firmware paths that aren’t exposed here.

## Installation

### Method 1: Using Python (Recommended)

1. **Install Python** (if not already installed):
   - Download from [python.org](https://www.python.org/downloads/)
   - During installation, check "Add Python to PATH"

2. **Download this application**:
   - Download all files to a folder (e.g., `C:\iPixel`)

3. **Install dependencies**:
   ```bash
   cd C:\iPixel
   pip install -r requirements.txt
   ```

4. **Run the application**:
   ```bash
   python ipixel_controller.py
   ```

### Method 2: Create a Standalone Executable (Optional)

To create a standalone .exe file that doesn't require Python:

1. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```

2. Create the executable:
   ```bash
   pyinstaller --onefile --windowed --name "iPixel Controller" ipixel_controller.py
   ```

3. Find the executable in the `dist` folder

## Usage

### 1. Connect to Your Device

1. Turn on your iPixel LED panel
2. Click **"Scan"** to search for nearby Bluetooth devices
3. Select your device from the dropdown (usually named "LED_BLE_...")
4. Click **"Connect"**
5. Wait for "Connected" status (green)

### 2. Send Text

1. Go to the **"Text"** tab
2. Enter your text in the text box
3. Choose text color (default: white)
4. Choose background color (default: black)
5. Select a sprite font (optional)
6. Click **"Send Text"**

**Tips:**
- Keep text short for better readability on small displays
- Smaller font sizes work better for longer text
- High contrast (white on black) is most readable

### 3. Display Images

1. Go to the **"Image"** tab
2. Click **"Load Image"** and select an image file
3. Preview appears in the window
4. Click **"Send Image"**

**Supported formats:** PNG, JPG, JPEG, GIF, BMP

**Tips:**
- Images are automatically resized to fit your panel
- For best results, use images with your panel's exact resolution
- Common panel sizes: 64x64, 32x32, 96x16

### 4. Show Clock

1. Go to the **"Clock"** tab
2. Select a clock style (0-8)
3. Click **"Show Clock"**

The clock will display the current time and update automatically.

### 5. Stock Market Display

1. Go to the **"📈 Stock"** tab
2. Enter a stock ticker symbol (e.g., AAPL, TSLA, GOOGL)
3. Click **"Fetch Stock Data"**
4. Choose your display format and colors
5. Click **"Send to Display"**
6. Enable auto-refresh to update prices automatically

**Note:** No API key required - uses yfinance library.

### 6. YouTube Stats

1. Go to the **"📺 YouTube"** tab
2. Enter your **YouTube API key** (get one from [Google Cloud Console](https://console.cloud.google.com/))
3. Enter a channel ID or @handle (e.g., @MrBeast)
4. Click **"Fetch Stats"**
5. Click **"Send to Display"**

**Format:** Logo + Subscribers only

### 7. Weather Display

1. Go to the **"🌤️ Weather"** tab
2. Enter your **OpenWeatherMap API key** (get free key from [openweathermap.org](https://openweathermap.org/api))
## Developer Notes

- Default assets live under `Gallery/` and are referenced with relative paths.
- Sprite fonts are managed in Settings → Sprite Fonts and stored in `ipixel_settings.json`.
- API keys are saved in `ipixel_secrets.json` (gitignored).

See [AGENTS.md](AGENTS.md) for internal architecture and contributor notes.
3. Enter your city name
4. Select temperature unit (°C or °F)
5. Click **"Fetch Weather"**
6. Choose display format
7. Click **"Send to Display"**

**Display formats:**
- Temperature + Condition
- Temperature Only
- City + Temperature
- Full (all info)

### 8. Pixel Art Animations

1. Go to the **"🎨 Animations"** tab
2. Choose an animation type:
   - **Conway's Game of Life**: Classic cellular automaton
   - **Matrix Rain**: Digital rain effect
   - **Fire Effect**: Realistic fire simulation
   - **Starfield**: Moving stars
   - **Plasma**: Colorful plasma effect
3. Select color scheme and speed (FPS)
4. Set duration (0 = infinite loop)
5. Click **"Start Animation"**

**Tips:**
- Higher FPS = smoother but more CPU intensive
- Game of Life density affects initial pattern complexity
- Use rainbow color for psychedelic effects

### 9. Adjust Settings

Go to the **"Settings"** tab to:
- **Adjust brightness**: Drag the slider (1-100%) and click "Set Brightness"
- **Power control**: Turn the display ON or OFF

## Troubleshooting

### Device Not Found During Scan

- Ensure your LED panel is powered on
- Check that Bluetooth is enabled on your PC
- Make sure the panel is not connected to another device
- Try moving the panel closer to your PC
- Restart both the panel and your PC

### Connection Failed

- Ensure no other app is connected to the panel (close the official iPixel app)
- On Windows, go to Settings → Bluetooth & devices → Remove the device, then scan again
- Try disabling and re-enabling Bluetooth
- Make sure your Bluetooth adapter supports Bluetooth LE (Low Energy)

### Text/Image Not Displaying

- Check that you're connected (status shows "Connected" in green)
- Try reducing font size or text length
- Ensure image file is not corrupted
- Try power cycling the panel

### "ModuleNotFoundError" Error

- Ensure you've installed all dependencies:
  ```bash
  pip install -r requirements.txt
  ```

### Slow Performance

- Close other Bluetooth applications
- Reduce image size before sending
- Move panel closer to PC for better signal

## API Keys Setup

### YouTube API Key

To use the YouTube Stats feature, you need a free YouTube Data API v3 key:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable **YouTube Data API v3**:
   - Go to "APIs & Services" → "Library"
   - Search for "YouTube Data API v3"
   - Click "Enable"
4. Create credentials:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "API Key"
   - Copy the generated key
5. Paste the key in the app's YouTube tab and click "Save Key"

**Note:** Free tier includes 10,000 quota units/day (sufficient for personal use).

### OpenWeatherMap API Key

To use the Weather Display feature, you need a free OpenWeatherMap API key:

1. Go to [openweathermap.org](https://openweathermap.org/api)
2. Click "Sign Up" and create a free account
3. Go to your account → "API keys"
4. Copy the default API key (or create a new one)
5. Paste the key in the app's Weather tab and click "Save Key"

**Note:** Free tier includes 1,000 API calls/day and updates every 10 minutes.

## Technical Details

### Supported Devices

This application works with LED panels using the iPixel Color protocol via Bluetooth LE:
- BGLight LED Pixel Boards
- B.K. Light LED Pixel Board (from Action stores)
- Generic LED_BLE_* devices
- iPixel Color compatible displays

### Protocol Information

- **Communication**: Bluetooth Low Energy (BLE)
- **Write UUID**: `0000fa02-0000-1000-8000-00805f9b34fb`
- **Notify UUID**: `0000fa03-0000-1000-8000-00805f9b34fb`
- **Library**: Built on [pypixelcolor](https://github.com/lucagoc/pypixelcolor)

## Development

### Project Structure

```
ipixel-controller/
├── ipixel_controller.py   # Main application
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

### Dependencies

- `pypixelcolor` - Core library for iPixel protocol
- `bleak` - Bluetooth Low Energy library
- `pillow` - Image processing

### Contributing

Feel free to submit issues or pull requests!

## Known Limitations

- Windows only (Linux/Mac support possible with modifications)
- Single device connection at a time
- Some advanced features from the official app may not be available
- Bluetooth range is limited (typically 10 meters)

## Credits

- Built on [pypixelcolor](https://github.com/lucagoc/pypixelcolor) by lucagoc
- Based on reverse-engineered iPixel protocol
- Thanks to the Home Assistant [ha-ipixel-color](https://github.com/cagcoach/ha-ipixel-color) project for protocol documentation

## License

This project is provided as-is for personal use. Not affiliated with iPixel or the original device manufacturers.

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Verify you're using the latest version
3. Check the pypixelcolor documentation
4. Open an issue on GitHub (if applicable)

---

**Enjoy controlling your LED panel!** 🎉
