# TELE4632 project
This project requires:
Flask
Ryu controller
Mininet

##Runing the Project
Flask application
```bash
export FLASK_APP=flaskFinal.py
flask run
```

Ryu controller
```bash
ryu-manager ryuFinal.py
```

Mininet topology
```bash
sudo python3 mininettopo.py
```

Website
```bash
xdg-open indexFinal.html
```

After executing the above commands in sequence, you can operate in the opened web page.
The login email is: test@example.com
The password is: password123

You can simulate rapid traffic consumption using the following scripts：

Test quota
```bash
python3 testquota.py
```

