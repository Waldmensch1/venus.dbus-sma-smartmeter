# venus.dbus-sma-smartmeter
A service for Venus OS, reading smart meter data from a SMA system (SMA-EM Speedwire Broadcast) and making the values available on dbus.

The Python script listen to the SMA-EM broadcast and publishes information on the dbus, using the service name com.victronenergy.grid. This makes the Venus OS work as if you had a physical Victron Grid Meter installed.

### Configuration

Not needed

### Installation

1. Copy the files to the /data folder on your venus:

   - /data/dbus-sma-smartmeter/dbus-sma-smartmeter.py
   - /data/dbus-sma-smartmeter/kill_me.sh
   - /data/dbus-sma-smartmeter/service/run

2. Set permissions for files:

   `chmod 755 /data/dbus-sma-smartmeter/service/run`

   `chmod 744 /data/dbus-sma-smartmeter/kill_me.sh`

3. Get two files from the [velib_python](https://github.com/victronenergy/velib_python) and install them on your venus:

   - /data/dbus-sma-smartmeter/vedbus.py
   - /data/dbus-sma-smartmeter/ve_utils.py

4. Add a symlink to the file /data/rc.local:

   `ln -s /data/dbus-sma-smartmeter/service /service/dbus-sma-smartmeter`

   Or if that file does not exist yet, store the file rc.local from this service on your Raspberry Pi as /data/rc.local .
   You can then create the symlink by just running rc.local:
  
   `rc.local`

   The daemon-tools should automatically start this service within seconds.

### Debugging

You can check the status of the service with svstat:

`svstat /service/dbus-sma-smartmeter`

It will show something like this:

`/service/dbus-sma-smartmeter: up (pid 10078) 325 seconds`

If the number of seconds is always 0 or 1 or any other small number, it means that the service crashes and gets restarted all the time.

When you think that the script crashes, start it directly from the command line:

`python /data/dbus-sma-smartmeter/dbus-sma-smartmeter.py`

and see if it throws any error messages.

If the script stops with the message

`dbus.exceptions.NameExistsException: Bus name already exists: com.victronenergy.grid"`

it means that the service is still running or another service is using that bus name.

Within repo you find a script speedwire_test.py . You can run it on your target machine to see whether UDP Broadcast is received. The script just listen an print received values on console. There is no dependency to VenusOS, means it should run on any Linux box where Python is installed
#### Restart the script

If you want to restart the script, for example after changing it, just run the following command:

`/data/dbus-sma-smartmeter/kill_me.sh`

The daemon-tools will restart the scriptwithin a few seconds.

### Hardware

It should work with
- SMA-EM10
- SMA-EM20
- SHM-2.0