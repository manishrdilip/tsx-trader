# Running the India trader on a cloud server (AWS Lightsail or DigitalOcean)

Same jobs as `india_laptop/`, run by cron on Ubuntu in India time:
8:15 token refresh, 9:10 order monitor, 9:15-3:35 auto-trader every 5 min (Mon-Fri).

## Step 1: Create the server (about US$5/month)

**DigitalOcean (simplest):** create an account -> Create -> Droplets -> Region **Bangalore (BLR1)**,
Image **Ubuntu 24.04**, plan **Basic, Regular, 1 GB RAM**, Authentication **Password** (set a long one)
-> Create. Its IPv4 address is fixed for as long as the droplet exists.

**AWS Lightsail:** lightsail.aws.amazon.com -> Create instance -> Region **Mumbai (ap-south-1)**,
Linux/Unix, **Ubuntu 24.04**, plan **US$5** (1 GB) -> Create. Then Networking -> **Create static IP**
and attach it to the instance (free while attached; the default IP changes if you stop the server).

## Step 2: Register the server's IP with Zerodha

developers.kite.trade -> My apps -> your app -> add the server's public IPv4 to the IP whitelist.

## Step 3: Set it up (about 15 minutes)

Log in: DigitalOcean -> droplet -> **Console**; Lightsail -> **Connect using SSH** (browser window).
Then run, one at a time:

    sudo apt-get update && sudo apt-get install -y git
    git clone https://github.com/manishrdilip/tsx-trader.git
    cd tsx-trader
    sudo bash india_server/setup.sh

Fill in the keys when the editor opens (Ctrl+O, Enter, Ctrl+X to save). Setup ends with a test that
places **no orders**; you should get 🔑 *token refreshed* and ✅ *connected to Zerodha (IP ...)*
on Telegram. The IP in that message must match the one registered in step 2.

## Every day

Nothing. Logs: `~/tsx-trader/india_server/logs`. Jobs: `crontab -l`.
Manual token refresh: `~/tsx-trader/india_server/run_task.sh refresh`.
Update keys: `nano ~/tsx-trader/.env`.
