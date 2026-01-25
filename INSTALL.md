# iPixel LED Panel Controller - Installation Guide

Quick and easy installation guide for users.

## System Requirements

- **Windows 10/11** (with Bluetooth support)
- **Python 3.8 or higher** - [Download here](https://www.python.org/downloads/)
- **iPixel Color 64x16 LED Panel** (Bluetooth LE)

## Installation Steps

### 1. Install Python

1. Download Python from [python.org/downloads](https://www.python.org/downloads/)
2. **IMPORTANT**: Check "Add Python to PATH" during installation
3. Verify installation by opening Command Prompt and typing:
   ```
   python --version
   ```

### 2. Download iPixel Controller

1. Download or clone this repository to your computer
2. Extract to a folder (e.g., `C:\iPIXEL Control`)

### 3. Install Dependencies

Open Command Prompt in the iPixel Control folder and run:

```bash
python -m pip install -r requirements.txt
```

This will install:
- `pypixelcolor` - LED panel control library
- `bleak` - Bluetooth communication
- `Pillow` - Image processing
- `yfinance` - Stock market data
- `google-api-python-client` - YouTube API
- `requests` - Weather API
- `numpy` - Animation calculations

### 4. Configure API Keys (Optional)

For YouTube Stats and Weather features, you'll need free API keys:

#### YouTube Data API v3
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable "YouTube Data API v3"
4. Create credentials (API Key)
5. The app will prompt you to enter it on first use

#### OpenWeatherMap API
1. Sign up at [OpenWeatherMap](https://openweathermap.org/api)
2. Get your free API key
3. The app will prompt you to enter it on first use

**Note**: Your API keys are stored locally in `ipixel_settings.json` and are never shared.

## Running the App

### Method 1: Python Launcher (Recommended)

Simply double-click:
```
run.py
```

This launcher will:
- ✓ Check your Python version
- ✓ Verify all dependencies
- ✓ Show helpful error messages if something is missing
- ✓ Launch the controller

**If Windows blocks it:**
1. Right-click `run.py` → "Open with" → "Python"
2. Or run from Command Prompt: `python run.py`

### Method 2: Direct Launch

Open Command Prompt in the app folder and run:
```bash
python ipixel_controller.py
```

### Method 3: Create Desktop Shortcut

1. Right-click on Desktop → New → Shortcut
2. Browse to your `run.py` file
3. Click Next, name it "iPixel Controller", Finish
4. Right-click shortcut → Properties
5. Change "Target" to: `pythonw.exe "C:\path\to\run.py"`
6. Change "Start in" to: `C:\path\to\iPIXEL Control`
7. Click OK

## Troubleshooting

### "Smart App Control blocked run.bat"

Windows Smart App Control may block `.bat` files. Solutions:

1. **Use `run.py` instead** (recommended) - Python files are not blocked
2. **Or**: Right-click run.bat → Properties → Check "Unblock" → Apply
3. **Or**: Settings → Privacy & Security → Smart App Control → Turn off (not recommended)

### "Python not found"

Make sure Python is in your PATH:
1. Search Windows for "Environment Variables"
2. Click "Environment Variables"
3. Under "System variables", find "Path"
4. Make sure Python installation folder is listed (e.g., `C:\Users\YourName\AppData\Local\Programs\Python\Python311`)

### "Module not found" errors

Reinstall dependencies:
```bash
python -m pip install --upgrade -r requirements.txt
```

### Bluetooth connection issues

1. Make sure Bluetooth is enabled on your PC
2. iPixel panel should be powered on
3. Click "Scan" to find devices
4. Select your device and click "Connect"

### API features not working

1. Check your API keys in Settings tab
2. For OpenWeatherMap: Wait 1-2 hours after creating key for activation
3. Test your internet connection

## First Time Setup

1. **Launch the app** using `run.py`
2. **Enable Bluetooth** on your PC
3. **Power on** your iPixel LED panel
4. Click **"Scan"** to find your device
5. Select your device and click **"Connect"**
6. Start creating content!

## Features

### Core Features (No API needed)
- ✅ **Text Display** - Scrolling text with colors & animations
- ✅ **Images** - Display custom images/GIFs
- ✅ **Clock** - Live time display or countdown timer
- ✅ **Text+Image Overlay** - Combine text and images
- ✅ **Brightness Control** - Adjust LED brightness
- ✅ **Presets** - Save and recall your favorite configurations
- ✅ **Playlists** - Auto-rotate through presets

### Advanced Features (API keys required)
- 📈 **Stock Market** - Live stock prices (uses yfinance, no key needed)
- 📺 **YouTube Stats** - Channel/video statistics (requires YouTube API key)
- 🌤️ **Weather Display** - Current weather conditions (requires OpenWeatherMap key)
- 🎨 **Pixel Animations** - Game of Life, Matrix, Fire, Starfield, Plasma

## Support

For issues or questions:
1. Check this guide thoroughly
2. Make sure all dependencies are installed
3. Try running from Command Prompt to see error messages
4. Check that your Python version is 3.8 or higher

## Privacy & Security

- ✅ All API keys stored locally in `ipixel_settings.json`
- ✅ No data is sent to external servers (except API calls you configure)
- ✅ No telemetry or tracking
- ✅ Open source - review the code yourself!

## License

Free to use and modify for personal use.
