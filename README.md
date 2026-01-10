# CampNet Auto Login

A lightweight Windows tray application that automatically logs you into a captive-portal Wi-Fi network (such as campus networks), with manual controls, safety checks, and zero unnecessary requests when you’re off-campus.

Designed to be:

- Reliable for long sessions
- Safe (no random logouts, no request spam)
- Privacy-respecting (no GPS / location APIs)
- Easy to run as a background app or startup service

---

## ✨ Features

- Auto login to captive portal Wi-Fi
- Manual **Force Logout** (pauses auto login)
- Manual **Force Login** (resumes auto login)
- Tray icon with live status tooltip
- Rotating log files (no clutter)
- No flashing console windows (even in `.exe`)
- Runs automatically on Windows startup

---

## 📒 TODO

- Add the start at startup option through config or menu item?
- Add much more detailed logging, especially for log status for production debugging and bug recreation.
- Version releasing to remove the need to have python installed to build.
- More constants shifted to config file for more control to the user.
- Better icon (maybe dynamic with status)
- Better guide to setup, with possible less steps and more images.

---

## 📁 Project Files

Files kept in the repository:

```
campnet_autologin.py
config.example.json
requirements.txt
README.md
.gitignore
```

Generated locally (not committed):

```
CampNetAutoLogin.exe
config.json
campnet_autologin.log
```

---

## 🧩 Requirements (Python run)

- Windows 10 / 11
- Python 3.10+ (official Python installer)
- Campus Wi‑Fi with captive portal

Install dependencies:

```bash
py -m pip install -r requirements.txt
```

---

## ⚙️ Configuration

### 1. Create `config.json`

Copy the example file:

```bash
copy config.example.json config.json
```

Edit `config.json` with your credentials and allowed SSIDs, for example:

```json
{
  "username": "YOUR_USERNAME",
  "password": "YOUR_PASSWORD",
  "check_interval": 10
}
```

---

## ▶️ Run using Python (development mode)

```bash
python campnet_autologin.py
```

Expected behavior:

- Tray icon appears
- Tooltip shows current status
- Logs written to `campnet_autologin.log`

Exit using:

- Tray → Exit
- `Ctrl + C` in terminal

---

## 📦 Build Windows `.exe` (recommended)

Creates a single background executable (no Python needed at runtime).

### 1. Install PyInstaller

```bash
py -m pip install pyinstaller
```

### 2. Build the executable

```bash
py -m PyInstaller --onefile --noconsole --name CampNetAutoLogin campnet_autologin.py
```

Output:

```
dist/CampNetAutoLogin.exe
```

---

## 📂 Final install layout (IMPORTANT)

Create a permanent folder, for example:

```
C:\Users\<YOUR_NAME>\Apps\CampNetAutoLogin\
```

Place **only these files** inside:

```
CampNetAutoLogin.exe
config.json
```

- `config.json` **must be next to the exe**
- Log files are created here automatically

---

## 🔁 Enable auto-start on Windows (recommended)

### Use Task Scheduler

1. Press **Win + R**
2. Type `taskschd.msc`
3. Click **Create Task…**

#### General tab

- Name: `CampNet Auto Login`
- Run only when user is logged on

#### Triggers tab

- New → **At log on**

#### Actions tab

- Action: **Start a program**
- Program/script:

  ```
  C:\Users\<YOUR_NAME>\Apps\CampNetAutoLogin\CampNetAutoLogin.exe
  ```

- Start in:

  ```
  C:\Users\<YOUR_NAME>\Apps\CampNetAutoLogin
  ```

#### Conditions tab

- Uncheck **Start only if on AC power**

Click **OK**.

Test by right-clicking the task → **Run**.

---

## 🖱️ Tray Menu Controls

Right-click the tray icon:

- **Force Login** — Enables auto login and immediately attempts login.
- **Force Logout (Pause Auto Login)** — Logs out and pauses all auto login attempts.
- **Exit** — Cleanly shuts down the app.

Hover over the tray icon to see live status.

---

## 📄 Logs

- File: `campnet_autologin.log`
- Automatically rotated
- Max size ~0.5 MB
- One backup kept

Safe for long-running sessions.

---

## 🔒 Privacy & Safety

- No GPS usage
- No Windows Location Service APIs
- No Wi‑Fi scanning

---

## 🛑 Troubleshooting

**App exits immediately**

- Ensure `config.json` exists
- Check JSON syntax

**No auto login**

- Verify SSID spelling
- Verify credentials
- Check log file

**Tray icon visible but no window**

- This is expected behavior

---

## ⚠️ Disclaimer

For personal use on networks where you are authorized to log in.
Do not use to bypass network policies.

---

## 🧠 Motivation

Campus captive portals are annoying.
This removes the friction without being invasive, spammy, or unsafe.
