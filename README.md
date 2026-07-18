# MtG Momir Printer

Software for playing the custom **Momir (Basic)** game mode of *Magic the Gathering* with a printer connected to a *Raspberry Pi* to enable playing this game mode in paper. This boils down to the user choosing a mana value and the system selecting a random creature card with the given mana value and printing that card so it can be used in paper play.

### Features

- Select a random creature card of a given mana value and print it
- Print the Momir Vig Avatar card
- Show relevant current card info on the display
- 2 printing modes: complete card images or text with art image for better readability
- Updates all relevant data when having internet connection
- Allows for complete offline use after initial connection
- Runs on low-end devices (Raspberry Pi 1 Model B)
- Designed for convenient use with rotary button and display
- Convenient shutdown and reboot options

## How to use / Instructions

If everything is set up, here is what you can do with the program:
- Turn rotary button to select a mana value
- Press rotary button to print a random creature card with the selected mana value
- Press LED button to show last printed card info on display
- Double-press rotary button to print Momir Vig Avatar
- Double-press LED button to switch to a text-based mode (for better readability)
  - Double-press again to switch back to the full-image mode
- Long-press (3s) LED button to shut down system
- Long-press (3s) rotary button to restart the program

## Setup

Setup consists of the hardware used and the software running on it. I configured and tested everything only for my specific hardware setup which is listed below. You can customize it if your setup is different.

### Hardware Requirements & Setup

List of relevant hardware parts used:
- Raspberry Pi 1 Model B (with storage medium for OS and data)
- Thermal Printer QR204 58mm
- OLED Display CH1116 1,54" 4 pin monochrome (128x64)
- Rotary Encoder KY-040
- Push Button with LED (self-reset)
- 9V power source (delivering 2A) for printer and 5V power source for everything else (I use a UPS with both outputs)
- optional: WIFI adapter for connectivity (otherwise Ethernet-cable)

Connect everything as shown in the wiring diagram. You can use a different pin setup, but the printer must be connected to the UART pins and the display to the I2C pins. 
My LED button has for outputs with two of these being mass for the button and LED, respectively; it's okay if your button only has three pins.

![Wiring Diagram](/misc/Wiring.png)

Many choices including the OS depended on the very limited hardware. Flash DietPi on your storage medium and start the RPI. Make sure you have internet access on the device until after you have successfully started the main program at least once.

<details>
<summary>Optional: Setting up WIFI</summary>

Prerequisites depend on the dongle you have. I have a cheap one and fortunately I did not have to install any drivers manually.

- see if net adapter (wlan0) available: ip link show
	- see if device available: lsusb
- show networks: iw wlan0 scan | grep SSID:
- edit /etc/wpa_supplicant.conf add network={ ssid="" psk="" }
	- multiple networks below each other, higher networks have priority
	- add network per command:  wpa_passphrase {name} {pw} >> /etc/wpa_supplicant/wpa_supplicant.conf
	- set update_config=1 option to 0 so list isn't automatically cleared
- connect with: wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant/wpa_supplicant.conf 
- get ip: dhclient wlan0
- see connected network: iw dev wlan0 link | grep SSID:
- if problems check network config in /var/network/interfaces
- disable usb powersave/autosuspend: echo -1 > /sys/module/usbcore/parameters/autosuspend    (value is 2 by default)
	- needs to repeated every startup so write service to set value: 
		- create service file disable-wifi-powersave.service:
		  \[Unit]
		  Description=disable-wifi-powersave
		  \[Service]
		  Type=oneshot
		  ExecStart={command from above}
		  \[Install]
		  WantedBy=multi-user.target     (default value but required)
		- copy file to services: cp {name}.service /etc/systemd/system/
		- enable: systemctl enable {service-name.service}

</details>

<details>
<summary>Custom considerations</summary>

Depending on the specifications of your printer and display, you need to change their configurations in the respective printer.py and display.py files. If you undervolt your printer, you might want to change the contrast and threshold on the black/white images in process_images.py. For me, the printer worked almost well enough on 5V even though it is below official specs.

If you use a different RPi model or OS, you might have to change to GPIO bouncetimes if you don't use LGPIO. You also might want to increase the batch sizes in the load_scryfall_data.py download functions if you device is more recent and you want faster speeds. You must change the GPIO pin setup accordingly if you deviate from the provided wiring diagram.

If your device has very limited storage (<8GB, maybe 4 GB suffice), you might have to change how data is stored. This program keeps all downloaded images in all versions; by only saving the color images temporary storage can be saved.

</details>

### Software Installation

You must install python and probably some libraries + configuration to get the hardware to work.

<details>
<summary>Setup GPIO</summary>

- install compatible rpi.gpio version: pip install rpi-lgpio
  - always use prefix "RPI_LGPIO_REVISION="800012" python3" for starting scripts so lgpio knows rpi 1b model is used
  - add to global env permanently in: nano /etc/profile , then in file: export {name=value}
  - make available to sudo: run visudo cmd and add line with: Defaults env_keep += {var_name}
  - check is available with: printenv

</details>

<details>
<summary>Setup Printer</summary>

- active uart in dietpi-config -> advanced -> serial/uart
- install missing libraries for pillow to work (view updated package names [here](https://pillow.readthedocs.io/en/stable/installation/building-from-source.html#external-libraries)): apt install build-essential libjpeg8-dev libtiff5-dev libopenjp2-7-dev libxcb1-dev libfreetype6-dev
- install in venv: pip install python-escpos\[serial]
- check if exists: dmesg | grep tty
	- should be ttyAMA0 but serial0 should always point there too (see ls -l /dev)
- add user: usermod -a -G dialout {user}

</details>

<details>
<summary>Setup Display</summary>

- active i2c in dietpi-config -> advanced -> i2c
- add user: usermod -a -G i2c {user}
- view device and adress: i2cdetect -y 1
	- adress should be 3c and needs to be specifiec in python display init
- install luma: pip install luma.oled
- display is actually ch1116 so use luma sh1106 class, but in there (oled>device>init.py) is display func change self.command(set_page_address, 0x02, 0x10) to self.command(set_page_address, 0x00, 0x10)

</details>

<details>
<summary>Create autostart service</summary>

TODO

</details>

## Start the program

After everything is set up, clone/copy this code and run `pip install .`. You can then run this program via `python main.py`. If everything works, you can set up a system service to run the program automatically after every system boot (see above).

If you want to skip card data updating, add the `-s` flag. Note that the program must be started without this flag at least once to initially download the required card data and images.

You can also specify which card images you want to download if you are only interested in one of the two available print modes. Use the `-t` flag with the argument `border_crop` if you only want the full image mode or use the argument `art_crop` if you only want the more readable text-based mode.

## Program Flow & Options

1. After start, the program first enters initialization of its components, mainly hardware
   - -> The LED starts blinking; hold button pressed if you want to skip the next step
2. Next, the program attempts to update its data if connected to the internet. This can be skipped by holding LED button pressed on startup
   1. If a newer bulk data version is available, the bulk data for all cards is downloaded
   2. Next, this data is loaded into the DB
   3. Then, the images for all cards are downloaded (for each print mode)
   4. Finally, the images are processed for printing and the new versions are saved (for each print mode)
3. The program enters the main loop where the user can interact with it (the LED is now permanently on to signal the program is ready). See instructions
4. If shutdown is requested, the program is gracefully stopped and the system shuts down. If restart is requested, the program restarts instead, starting from step 1

If an error is encountered at any step and the program cannot resolve it, it restarts itself, but not the system. Step 2 is skipped during such program restarts. If the program is stuck in a faulty state and restarts in a loop, the LED button can be held pressed during the restart announcement on the display to cancel it and shut the system down instead.

## Update to future versions of the game

Magic is a permanently evolving game, introducing new mechanics and card types which may require adapting this software. Below is a list of aspects that could potentially require adjustments: 
- queries.py: new card layouts with multiple faces (beyond transform, modal_dfc, prepare, etc.) have to be added to the constants and new categories might need to be handled in get_random_creature_card() and get_standardized_card_dict()
- load_scryfall_data.py: the ALLOWED_CARDS list and the legal card filter in _is_card_valid() if more or less cards should be indexed
  - all other constants based on the Scryfall API spec, but these are unlikely to change
