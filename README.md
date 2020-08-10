Discord Art Sumbission Bot!
=============
<a href="https://patreon.com/boiboi"><img src="https://img.shields.io/endpoint.svg?url=https%3A%2F%2Fshieldsio-patreon.herokuapp.com%2Fbotboi&style=for-the-badge" /> </a>

## Spinning up your own instance of Hilda-bot
###Prerequisites
* Python 3.6 Must be installed ([Read how to check installed version (Mac or PC)](https://www.wikihow.com/Check-Python-Version-on-PC-or-Mac))
* Ensure pip is up to date
* Ensure git is installed: `git --version`

**For the rest of this guide we will assume running `python` in your terminal/command line will start python 3.6.**
```commandline
python -m pip install --upgrade pip
```
  
###Next
1. First clone the repository onto your computer

```commandline
git clone https://github.com/jcsumlin/Hilda-Bot.git
```

2. Create the Database
```commandline
python create_database.py
```
***NOTE: This only has to be run this once***
1. Make sure that the database.db file is in the cogs folder
1. Create your own `auth.ini` file from the `auth.ini.example` example using this command
```
cp auth.ini.example auth.ini
```
1. Fill out the new `auth.ini` file and exit to the root directory
1. Run the `main.py` file using the following command `python main.py`
1. Done!

If you wish to keep this bot running and you're using linux's ubuntu as your os I would recommend looking into screens
```commandline
sudo apt-get install screen
``` 
## **License**
Copyright 2020 [jcsumlin](https://github.com/jcsumlin)

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
