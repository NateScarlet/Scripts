setx http_proxy localhost:1080
setx https_proxy localhost:1080
git config --global http.https://golang.org.proxy localhost:1080
git config --global http.https://go.googlesource.com.proxy localhost:1080
git config --global http.https://go.googlesource.com.sslVerify false