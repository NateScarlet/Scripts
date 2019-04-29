cmd /c setup_gitproxy.cmd
git config --global core.editor "code.cmd --wait --reuse"
git config --global core.autocrlf input
git config --global push.followTags true
git config --global alias.amend "commit --amend --no-edit"
REM https://hub.github.com/hub.1.html
git config --global hub.protocol https
REM https://stackoverflow.com/questions/14937405/npm-git-protocol-dependencies
git config --global url."https://github.com/".insteadOf git@github.com:
git config --global url."https://".insteadOf git://
