# Raspberry Pi Setup

## Install

```bash
git clone https://github.com/maijime/vending-inv.git
cd vending-inv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env` with your credentials (see README).

## Initialize Database

Option A — fresh start:
```bash
python3 database.py
python3 load_historical.py 2024-07-01 2026-03-19
```

Option B — copy from your Mac:
```bash
scp user@mac:~/code/py/vending-inv/vending.db ~/vending-inv/
```

## Dashboard (systemd)

Create `/etc/systemd/system/vending.service`:

```ini
[Unit]
Description=Vending Dashboard
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/vending-inv
ExecStart=/home/pi/vending-inv/.venv/bin/python3 app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable vending
sudo systemctl start vending
```

## Daily Automation (cron)

```bash
crontab -e
```

Add:
```
15 16 * * 1-5 cd /home/pi/vending-inv && .venv/bin/python3 daily_automation.py >> logs/cron.log 2>&1
```

## Remote Access (Tailscale)

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Access dashboard from anywhere: `http://<pi-tailscale-ip>:5001`
