SET "MarkFile="%~1\修图 Nate.txt""
ECHO 修图:Nate Scarlet 邮箱：NateScarlet@Gmail.com >> %MarkFile%
ECHO 	非工作日乐意承接任何无偿漫画修图 通常于收到24小时内完成 >>%MarkFile%
ECHO 								%DATE% %TIME% >>%MarkFile%
SET "zip="%ProgramFiles%\7-Zip\7z.exe""
%zip% a "%~dp1[修图]%~n1.zip" "%~1\"
DEL %MarkFile%