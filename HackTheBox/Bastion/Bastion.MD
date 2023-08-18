# Bastion [htb](https://app.hackthebox.com/machines/Bastion)
![bastion-01]()


## Recon

Lets add the target to our `/etc/hosts` file:

![hosts-02]()


Now we can enumerate the target with:

`nmap -sC -sV -A -p- bastion.htb -oN nmap.result`

![nmap-res-03]()

We have the following:

+ SSH on port 22. 
+ RPC endpoint mapper on port 135.
+ Netbios on port 139. 
+ SMB on port 445. 
+ HTTP API ports 5985 and 47001. 
+ Other RPC related ports. 

The target seems to be running a 2016 Windows server. Lets start by taking a look at the SMB, perhaps we
can access resources without authentication? After that well take a look at the HTTP API ports. 


## SMB port 445

Lets see if we can list out the shares with a null session:

`smbclient -N -L \\\\bastion.htb\\`

![shares-04]()

Yes we can, this is bad. If we can list information without authintication we can probably connect 
to a share as well. lets try the the `Backups` share:

`smbclient --no-pass //bastion.htb/Backups`

![backups-05]()

We can see we have a `WindowsImageBackup` folder a `.tmp` file and a `note.txt`
The note simply tells us not to copy the eniter Backups share through the VPN:

![note-06]()

The `.tmp` file is empty, but the most interesting thing here is the `WindowsImageBackup` folder. 
If we `cd` into the following path inside it with: 

`cd \WindowsImageBackup\L4mpje-PC\"Backup 2019-02-22 124351"`

Then run `ls` we can see the following:

![vhd-07]()

There are more `.xml` files below, but we are primarly interested in thoes `.vhd` files. 
VHD (Virtual Hard Disk) files are disk image formats that store a computer's entire hard drive.

The first disk is the boot sector, ive had a look around it, not much there. The second disk is what we want. 

Once we download the disk to your kali machine, we can examine the `.vhd` files with a 
suite of tools called `libguestfs-tools`, you may need to install this on your system with:

`apt install libguestfs-tools`.

Now we can list out the partitions on the virtual disk with:

`virt-filesystems -a 9b9cfbc4-369e-11e9-a17c-806e6f6e6963.vhd`

![partitions-08]()


Only one partition, Lets mount it with:

`guestmount -a 9b9cfbc4-369e-11e9-a17c-806e6f6e6963.vhd -m /dev/sda1 --ro /mnt/bastion`

If you pay close attention, youll notice this is the Windows OS installation folder (the C drive).
This means that the SAM file is in here. If we cd into:

`Windows/System32/config`

We can see the SAM file, along with the syskey to read it: 

![sam-09]()

Now all we need to do to read this file is use `samdump2`:

`samdump2 SYSTEM SAM`

![samdump-10]()

I've tried to use `psexec` to get a shell with the NTLM hash, but that failed. I also tried other tools from the `impacker` suite, but nothing worked. So i decided to decrypt the NTLM hash locally and try to log in to the SSH. 

First, save the NTLM portion of the hash to a file: 

`echo '26112010952d963c8dc4217daec986d9' > ntlm_hash.txt`

Next, use `john` to decrypt the hash:

`john --wordlist=/usr/share/wordlists/rockyou.txt --format=NT ntlm_hash.txt`

![decrypt-11]()

Now we can login to the ssh:

![shell-12]()

## Privilege Escalation


If we take a look at our user's `AppData/Roaming` folder we can see an interesting app:

![remoteng-13]()

mRemoteNG is a fork of mRemote: an open source, tabbed, multi-protocol, remote connections manager for Windows. remote connection means passwords.


If we cd into this folder we can find the config file that stroes the accounts:

![app-dir-14]()

If we open this file we can see the following:

![admin-hash-15]()

The admin probably used this software to connect to the Domain Controller. Now we need to decrypt the 
password. 

If we search google we can find the following [Github](https://github.com/gquere/mRemoteNG_password_decrypt) This tool should help us decrypt the password. All we nned is to transfer the `confCons.xml` file to our kali machine. 

To do that i start an FTP server with:

`python -m pyftpdlib -p 21 --write`

Then i connect to the FTP from the windows target and copy the file over:

![ftp-16]()


Now we can decrypt the file with:

`./mremoteng_decrypt.py confCons.xml`

![decrypt-17]()


The low-level user password does match what we found earlier in the SAM file, lets try to connect to the 
SSH as the admin user: 

![root-18]()
