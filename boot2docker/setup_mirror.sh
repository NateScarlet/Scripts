echo http://mirrors.163.com/tinycorelinux/ | sudo tee /opt/tcemirror
echo '[global]
index-url = https://mirrors.aliyun.com/pypi/simple' | sudo tee /etc/pip.conf