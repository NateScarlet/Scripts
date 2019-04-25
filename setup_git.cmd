cmd /c setup_gitproxy.cmd
git config --global core.editor "code.cmd --wait --reuse"
git config --global core.autocrlf input
git config --global push.followTags true
git config --global alias.amend "commit --amend --no-edit"
REM https://hub.github.com/hub.1.html
git config --global hub.protocol https
