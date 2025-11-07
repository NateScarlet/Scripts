SET "PROXY=127.0.0.1:1080"
ping -n 1 golang.org || git config --global http.https://golang.org.proxy "%PROXY%"
ping -n 1 go.googlesource.com || git config --global http.https://go.googlesource.com.proxy "%PROXY%" && git config --global http.https://go.googlesource.com.sslVerify false
