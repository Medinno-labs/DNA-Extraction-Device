# DNA Extraction Device

This repository contains the touchscreen application and hardware-control code deployed on the Raspberry Pi (RPi). The application starts automatically after the Pi boots into its graphical desktop.

> **Deployment note:** The MedInno desktop wallpaper/logo and boot splash settings are configured in Raspberry Pi OS. They are not set by this Python application. The startup service launches the role-selection application after the desktop is available.

## Application flow

```text
Raspberry Pi boots
  └─ Raspberry Pi OS graphical desktop starts
      └─ systemd starts ui2.py
          ├─ User → user_ui.py
          └─ Admin → PIN screen → admin_ui.py
```

- **Role-selection screen (`ui2.py`)**: the first application screen. Users can enter the user interface directly. Admin access requires the PIN configured in `ui2.py`.
- **User interface (`user_ui.py`)**: streamlined interface for selecting a sample and controlling an extraction run. It omits admin-specific heating, fan, debug, Wi-Fi, and graph controls.
- **Admin interface (`admin_ui.py`)**: full interface, including extraction controls, heating/fan controls, debug and Wi-Fi tools, graph view, update, exit, restart, and shutdown.
- When an admin or user interface closes, `ui2.py` detects that its child process has exited and returns to role selection.

The user-facing sample menu currently includes Sputum, Blood RNA, Viral RNA, Cervical DNA, Blood DNA, DBS, Plant DNA, and a 15-second test option. The sample choices are connected to the sequence functions in the control modules below.

## Operator workflow

1. Select a sample in the operator interface.
2. Press **Start Extraction** and follow the on-screen confirmations, including the sleeve check.
3. The interface calls the selected sample's sequence function. Shared state, temperature/progress messages, and countdown behavior are managed through `common.py` and `timer_module.py`; motor and heater actions are performed by the control code and Raspberry Pi hardware.
4. Use **Pause/Resume** or **Stop Extraction** as needed. **Sleeve Change** stops the current run before starting the sleeve-change sequence. The admin interface can also show **Resume Run** when an interrupted run is available.

## Main files

| File | Purpose |
| --- | --- |
| `ui2.py` | PyQt5 role-selection and admin-PIN screen; launches the selected interface. |
| `admin_ui.py` | Full Tkinter operator/admin interface. |
| `user_ui.py` | Simplified Tkinter operator interface. |
| `common.py` | Shared GPIO, temperature, PID, extraction state, and device-control helpers. |
| `timer_module.py` | Shared extraction timer support. |
| `sputum_control.py`, `blood_control.py`, `blood_rna_control.py`, `viral_rna_control.py`, `cervical_control.py`, `dbs_control.py`, `plant_dna_control.py`, `test_control.py` | Sample-specific motor/extraction sequence functions used by the interfaces. |
| `debug_ui.py` | Admin-launched debugging interface. |
| `wifi_ui.py` | Admin-launched Wi-Fi interface. |
| `2_sensor.py` | Sensor/graph support launched from the admin graph screen. |
| `logo.png` | Logo displayed by `ui2.py`; keep it beside `ui2.py`. |
| `background image wit.png`, `logo_transparent.png` | Additional image assets used by the project. |
| `R_&_D_codes/` | Research, backup, and development code; not the startup entry point used by the service below. |

The graphical application depends on Raspberry Pi hardware and should be tested on the target device. Its Python modules use Tkinter, PyQt5, Pillow, `RPi.GPIO`, `simple-pid`, `board`/`busio`, and Adafruit's MLX90614 library. The optional graph/sensor feature additionally imports Flask, Flask-SocketIO, and `spidev`. Install packages for the same Python interpreter that the systemd service uses, and enable/configure the required Raspberry Pi GPIO and I²C hardware separately.

## Raspberry Pi startup service

The deployed service file is `/etc/systemd/system/ui2.service`. The example below reflects the current deployment details (`sppat` user and `/home/sppat/shubham` project directory). **Change the username and paths if installing elsewhere.**

```ini
[Unit]
Description=Tkinter UI on Startup
After=graphical-session.target

[Service]
ExecStart=/bin/bash -c 'sleep 5 && /usr/bin/python3 /home/sppat/shubham/ui2.py'
WorkingDirectory=/home/sppat/shubham
Restart=always
User=sppat
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/sppat/.Xauthority

[Install]
WantedBy=default.target
```

The five-second delay gives the graphical desktop time to become ready. `DISPLAY` and `XAUTHORITY` allow the service to open its Qt/Tk windows on that desktop. The `WorkingDirectory` and script path should point to the directory containing `ui2.py` and its related Python files and assets.

### Install or update the service

On the Pi, create or edit the service file:

```bash
sudo nano /etc/systemd/system/ui2.service
```

Paste the unit configuration above, adjusting paths and user as needed, then reload systemd and enable/start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ui2.service
sudo systemctl start ui2.service
```

Useful service commands:

```bash
sudo systemctl status ui2.service
sudo systemctl restart ui2.service
sudo systemctl stop ui2.service
sudo journalctl -u ui2.service -b --no-pager
```

The role-selection screen starts with `ui2.py`; it launches `admin_ui.py` or `user_ui.py` from the same directory as a child process. Child-process output is written to `/tmp/ui_launch.log`.

## Access codes and deployment-specific settings

- `ui2.py` currently defines the admin-entry PIN as `1234` (`ADMIN_PIN`).
- `admin_ui.py` and `user_ui.py` also define an exit PIN as `1234` (`EXIT_PIN`). Update all applicable values in the source before deployment if the device should use different PINs. These PINs are stored in the Python source code, not in a protected credential store.
- The Update button in `admin_ui.py` currently runs `git pull` in `/home/sppat/shubham`. If the checkout is installed at a different location, update the `repo_path` in `admin_ui.py`. The Pi also needs a working Git remote and network access for this feature.
- Keep the required Python files and image assets together in the application directory; the startup launcher looks for the UI scripts alongside `ui2.py`.

## Screenshots

Add deployment screenshots to `docs/images/` and link them here when available:

- `docs/images/role-selection.png` — user/admin selection screen.
- `docs/images/admin-pin.png` — administrator PIN screen.
- `docs/images/admin-ui.png` — full administrator interface.
- `docs/images/user-ui.png` — simplified user interface.

## Troubleshooting

- **The service is active but no UI appears:** confirm that the Pi has logged into the graphical desktop, that `DISPLAY=:0` and `XAUTHORITY` match that desktop session, and that the service user owns/has access to the project files.
- **The service fails to start:** inspect `sudo systemctl status ui2.service` and `sudo journalctl -u ui2.service -b --no-pager`; check that `/usr/bin/python3` and the configured `ui2.py` path exist.
- **The role-selection screen appears but a child screen does not:** check `/tmp/ui_launch.log`, confirm the selected UI script exists beside `ui2.py`, and install its imports for the Python interpreter running the service.
- **The logo is missing on the role-selection screen:** verify that `logo.png` is in the same directory as `ui2.py`.
- **GPIO or sensor features fail:** verify the device wiring, Raspberry Pi interfaces, permissions, and hardware-specific Python libraries. Do not test motor/heater functions without the appropriate device setup and operating procedure.
