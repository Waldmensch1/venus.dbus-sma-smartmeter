#!/usr/bin/env bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
SERVICE_NAME=$(basename $SCRIPT_DIR)

# set permissions for script files
chmod a+x $SCRIPT_DIR/kill_me.sh
chmod 744 $SCRIPT_DIR/kill_me.sh
chmod a+x $SCRIPT_DIR/service/run
chmod 755 $SCRIPT_DIR/service/run

#add dependencies
wget https://raw.githubusercontent.com/victronenergy/velib_python/master/vedbus.py
wget https://raw.githubusercontent.com/victronenergy/velib_python/master/ve_utils.py

# create symlink to run script as daemon
ln -s $SCRIPT_DIR/service /service/$SERVICE_NAME

# add install-script to rc.local to persist firmware updates
FILE_NAME=/data/rc.local
if [ ! -f $FILE_NAME ]
then
    touch $FILE_NAME
    chmod 755 $FILE_NAME
    echo "#!/usr/bin/env bash" >> $FILE_NAME
    echo >> $FILE_NAME
fi
grep -qxF "$SCRIPT_DIR/install.sh" $FILE_NAME || echo "$SCRIPT_DIR/install.sh" >> $FILE_NAME
