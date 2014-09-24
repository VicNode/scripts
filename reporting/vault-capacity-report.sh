#!/bin/bash

usage () {
    echo "Usage:"
    echo "${0} -d NUM_DISKS -n [HOSTS]"
    echo "e.g. ${0} -d 4 -n host1 host2"
    exit 1
}

get_disk_info () {
    server=${1}
    disk_num=${2}
    cmd="df /srv/node/disk${disk_num}"
    df_output=$(ssh "${server}" -o ConnectTimeout=1 -C "${cmd}" | tail -n 1)
}

nodes=""
let disks=0

while getopts ":n:d:" opt; do
    case "${opt}" in
        n)
            nodes="${nodes} ${OPTARG}"
            ;;
        d)
            disks="${OPTARG}"
            ;;
        *)
            usage
            ;;
    esac
done
shift $(( OPTIND - 1 ))
nodes="${nodes} $*"

if [ "${nodes}" == "" ] || [ ${disks} -eq 0 ] ; then usage ; fi

let total_capacity=0
let total_used=0
for node in ${nodes}; do
    for disk in $(seq 1 ${disks}); do

        get_disk_info ${node} ${disk}
        total_on_node=$(echo "${df_output}" | awk '{print $2}')
        used_on_node=$(echo "${df_output}" | awk '{print $3}')

        ((total_capacity += total_on_node))
        ((total_used += used_on_node))
    done
done

echo "raw, usable, used"
echo "$((total_capacity/1024/1024/1024)), $((total_capacity/2/1024/1024/1024)), $((total_used/2/1024/1024/1024))"
