setx http_proxy 127.0.0.1:1080
setx https_proxy 127.0.0.1:1080
setx no_proxy 127.0.0.1,192.168.*.*,localhost
git config --global http.https://golang.org.proxy 127.0.0.1:1080
git config --global http.https://go.googlesource.com.proxy 127.0.0.1:1080
git config --global http.https://go.googlesource.com.sslVerify false