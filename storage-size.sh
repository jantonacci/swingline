#!/bin/sh

# ATTN: Before pasting in vi, run...
# :set noai nocin nosi inde=

indent(){
  cat - | sed 's#^#=> #'
}

indentdbl(){
  cat - | sed 's#^#====> #'
}

timestamp(){
  datetime=$(date +"%Y-%m-%dT%H:%M:%SZ")
  host=$(hostname -s)
  script=$0
  prefix="$datetime $host:$script: "
  cat - | sed "s#^#$prefix#"
}

testsuite(){
  echo -e "CMD: 'localcli storage vmfs extent list' (no units, informational)"
  localcli storage vmfs extent list | grep -v " mpx\." | indent
  echo -e "CMD: 'localcli storage filesystem list' (bytes)"
  localcli storage filesystem list | grep -E "^(Mount|-)|VMFS" | indent
  echo -e "CMD: 'df /vmfs/volumes/*' (bytes)"
  df | grep -E "^(Filesystem|VMFS)" | indent
  echo -e "CMD: 'du -sx /vmfs/volumes/*' (kilobytes)"
  for VOL in $(localcli storage filesystem list | grep VMFS | awk '{print $1}'); do
    du -sx $VOL | indent
  done
  echo -e "CMD: 'localcli storage core device partition list' (bytes)"
  localcli storage core device partition list | grep -v "^mpx\.vmhba" | indent
  echo -e "CMD: 'partedUtil get[ptbl] /dev/disks/*' (sectors)"
  for DISK in $(ls /dev/disks/* | grep -Ev '/(vml|mpx)\..*|[0-9,a-c]:[0-9][0-9]*$'); do
    echo -e "partedUtil get $DISK" | indent
    partedUtil get $DISK | indentdbl
    echo -e "partedUtil getptbl $DISK" | indent
    partedUtil getptbl $DISK | indentdbl
  done
}

testsuite | timestamp
#EOF
