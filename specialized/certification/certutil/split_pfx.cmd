openssl pkcs12 -in csheet.pfx -clcerts -nokeys -out csheet.crt
openssl pkcs12 -in csheet.pfx -nodes -nocerts -out csheet.key