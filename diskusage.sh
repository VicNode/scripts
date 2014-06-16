#!/bin/bash
TOTALSTORAGE=$((0))
TOTALUSED=$((0))

#Six servers per site
for i in `seq 3 6`; 
do

    for j in `seq 1 4`;
    do
        COMMAND="df /srv/node/disk$j"
        DFTMP=`ssh root@swift$i-qh2.mgmt.storage.unimelb.edu.au -o ConnectTimeout=1 -C $COMMAND | tail -1`

        NODETOTAL=`echo $DFTMP | awk '{print $2}'`
        NODEUSED=`echo $DFTMP | awk '{print $3}'`
        TOTALSTORAGE=$(($TOTALSTORAGE + $NODETOTAL ))
        TOTALUSED=$(($TOTALUSED + $NODEUSED ))

        DFTMP=`ssh root@swift$i-np.mgmt.storage.unimelb.edu.au -o ConnectTimeout=1 -C $COMMAND | tail -1`

        NODETOTAL=`echo $DFTMP | awk '{print $2}'`
        NODEUSED=`echo $DFTMP | awk '{print $3}'`
        
        TOTALSTORAGE=$(($TOTALSTORAGE + $NODETOTAL ))
        TOTALUSED=$(($TOTALUSED + $NODEUSED ))

    done

done

echo "$((${TOTALSTORAGE}/1024/1024/1024)), $((${TOTALSTORAGE}/2/1024/1024/1024)), $((${TOTALUSED}/2/1024/1024/1024))"
