git config --global user.email "NateScarlet@Gmail.com"
git config --global user.name "NateScarlet"
git config --global core.editor "code.cmd --wait"
git config --global core.autocrlf input
git config --global commit.gpgsign true
git config --global tag.gpgsign true
git config --global user.signingkey 5C242793B070309C
git config --global gpg.program "C:\Program Files (x86)\GnuPG\bin\gpg.exe"
git config --global push.followTags true
git config --global alias.amend "commit --amend --no-edit"
REM https://hub.github.com/hub.1.html
git config --global hub.protocol https
REM https://stackoverflow.com/questions/14937405/npm-git-protocol-dependencies
git config --global url."https://github.com/".insteadOf git@github.com:
git config --global url."https://".insteadOf git://
